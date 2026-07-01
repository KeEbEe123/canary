"""Auto-instrument the OpenAI Python SDK (>=1.0).

``canary.instrument("openai")`` monkey-patches ``Completions.create`` and its
async twin so every chat completion becomes an ``llm`` span capturing the model,
prompt/completion tokens, latency, and an estimated USD cost. It is idempotent
and a safe no-op when ``openai`` is not installed.
"""

from __future__ import annotations

import time
from typing import Any

from ..client import _require_client

# USD per 1K tokens, (prompt, completion). Approximate, static, best-effort — a
# cost *estimate*, not billing. Unknown models fall back to a small default.
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-4": (0.03, 0.06),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "o1": (0.015, 0.06),
    "o1-mini": (0.003, 0.012),
}
_DEFAULT_PRICE = (0.001, 0.002)

_PATCHED = False


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough USD cost for a completion given its token counts."""
    key = next((m for m in _PRICES if model.startswith(m)), None)
    prompt_rate, completion_rate = _PRICES.get(key, _DEFAULT_PRICE) if key else _DEFAULT_PRICE
    return round(prompt_tokens / 1000 * prompt_rate + completion_tokens / 1000 * completion_rate, 6)


def _record(span: Any, model: str, response: Any, latency_ms: float) -> None:
    """Copy usage + cost off an OpenAI response onto the span."""
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    span.set_attribute("model", model)
    span.set_attribute("prompt_tokens", prompt_tokens)
    span.set_attribute("completion_tokens", completion_tokens)
    span.set_attribute("total_tokens", getattr(usage, "total_tokens", prompt_tokens + completion_tokens))
    span.set_attribute("latency_ms", round(latency_ms, 2))
    span.set_attribute("cost_usd", estimate_cost(model, prompt_tokens, completion_tokens))


def instrument_openai() -> None:
    """Patch OpenAI's completion methods. Idempotent; no-op if openai absent."""
    global _PATCHED
    if _PATCHED:
        return
    try:
        from openai.resources.chat import completions as _completions
    except Exception:  # noqa: BLE001 - openai not installed / incompatible
        return

    sync_create = _completions.Completions.create
    async_create = _completions.AsyncCompletions.create

    def wrapped_create(self: Any, *args: Any, **kwargs: Any) -> Any:
        client = _require_client()
        model = kwargs.get("model", "unknown")
        span, tokens = client.tracer.start_span(f"openai.{model}", kind="llm", model=model)
        span.set_input(kwargs.get("messages"))
        started = time.time()
        try:
            response = sync_create(self, *args, **kwargs)
            _record(span, model, response, (time.time() - started) * 1000)
            return response
        except BaseException as exc:  # noqa: BLE001 - re-raised
            span.record_error(exc)
            raise
        finally:
            client.tracer.end_span(span, tokens)

    async def wrapped_acreate(self: Any, *args: Any, **kwargs: Any) -> Any:
        client = _require_client()
        model = kwargs.get("model", "unknown")
        span, tokens = client.tracer.start_span(f"openai.{model}", kind="llm", model=model)
        span.set_input(kwargs.get("messages"))
        started = time.time()
        try:
            response = await async_create(self, *args, **kwargs)
            _record(span, model, response, (time.time() - started) * 1000)
            return response
        except BaseException as exc:  # noqa: BLE001 - re-raised
            span.record_error(exc)
            raise
        finally:
            client.tracer.end_span(span, tokens)

    _completions.Completions.create = wrapped_create  # type: ignore[assignment]
    _completions.AsyncCompletions.create = wrapped_acreate  # type: ignore[assignment]
    _PATCHED = True
