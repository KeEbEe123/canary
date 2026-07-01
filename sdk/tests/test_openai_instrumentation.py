"""Tests for OpenAI auto-instrumentation.

OpenAI isn't a test dependency, so we register a minimal fake ``openai`` module
shaped like the real one (``openai.resources.chat.completions`` with sync/async
``Completions.create``) and verify the wrapper captures model/tokens/cost.
"""

from __future__ import annotations

import sys
import types

import pytest

from canary.instrumentation.openai import estimate_cost


def test_estimate_cost_known_model():
    # gpt-4o: (0.0025, 0.01) per 1K tokens.
    cost = estimate_cost("gpt-4o", 1000, 1000)
    assert cost == pytest.approx(0.0025 + 0.01)


def test_estimate_cost_prefix_match_and_default():
    assert estimate_cost("gpt-4o-2024-08-06", 1000, 0) == pytest.approx(0.0025)
    # Unknown model falls back to the default price, never crashes.
    assert estimate_cost("some-future-model", 1000, 1000) > 0


class _Usage:
    def __init__(self) -> None:
        self.prompt_tokens = 120
        self.completion_tokens = 30
        self.total_tokens = 150


class _Response:
    usage = _Usage()


def _install_fake_openai() -> types.ModuleType:
    """Register a fake openai package tree and return the completions module."""
    completions = types.ModuleType("openai.resources.chat.completions")

    class Completions:
        def create(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return _Response()

    class AsyncCompletions:
        async def create(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return _Response()

    completions.Completions = Completions
    completions.AsyncCompletions = AsyncCompletions

    chat = types.ModuleType("openai.resources.chat")
    chat.completions = completions
    resources = types.ModuleType("openai.resources")
    resources.chat = chat
    openai = types.ModuleType("openai")
    openai.resources = resources

    sys.modules.update(
        {
            "openai": openai,
            "openai.resources": resources,
            "openai.resources.chat": chat,
            "openai.resources.chat.completions": completions,
        }
    )
    return completions


@pytest.fixture
def fake_openai(monkeypatch):
    import canary.instrumentation.openai as inst

    monkeypatch.setattr(inst, "_PATCHED", False)
    completions = _install_fake_openai()
    yield completions
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("openai."):
            del sys.modules[mod]


def test_instrument_openai_captures_llm_span(client, transport, fake_openai):
    import canary

    canary.instrument("openai")

    @canary.trace("chatbot")
    def run() -> None:
        fake_openai.Completions().create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])

    run()

    llm = transport.by_kind("llm")
    assert len(llm) == 1
    attrs = llm[0]["attributes"]
    assert attrs["model"] == "gpt-4o"
    assert attrs["prompt_tokens"] == 120
    assert attrs["completion_tokens"] == 30
    assert attrs["cost_usd"] == pytest.approx(estimate_cost("gpt-4o", 120, 30))


def test_instrument_openai_is_noop_when_absent(client, monkeypatch):
    # No fake installed → patching should silently do nothing, not raise.
    import canary.instrumentation.openai as inst

    monkeypatch.setattr(inst, "_PATCHED", False)
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("openai."):
            monkeypatch.delitem(sys.modules, mod, raising=False)
    inst.instrument_openai()  # should not raise
