"""LangChain integration via a callback handler.

Unlike OpenAI there's nothing global to monkey-patch — LangChain invokes
callbacks you register. Pass :class:`CanaryCallbackHandler` to any chain, agent,
or LLM (``callbacks=[CanaryCallbackHandler()]``) and its LLM calls, tool calls,
and errors become Canary spans. Soft-imports ``langchain_core`` so the SDK works
without LangChain installed.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - only exercised when langchain is installed
    from langchain_core.callbacks import BaseCallbackHandler as _Base
except Exception:  # noqa: BLE001
    _Base = object  # type: ignore[assignment, misc]


class CanaryCallbackHandler(_Base):  # type: ignore[misc, valid-type]
    """Maps LangChain lifecycle events onto Canary spans keyed by run id."""

    def __init__(self) -> None:
        # LangChain hands us a UUID per event; we map it to our live span/tokens.
        self._spans: dict[Any, tuple[Any, Any]] = {}

    def _client(self) -> Any:
        from ..client import _require_client

        return _require_client()

    # --- LLM ---------------------------------------------------------------

    def on_llm_start(self, serialized: dict, prompts: list[str], *, run_id: Any = None, **kw: Any) -> None:
        model = (serialized or {}).get("name", "llm")
        span, tokens = self._client().tracer.start_span(f"langchain.{model}", kind="llm", model=model)
        span.set_input(prompts)
        self._spans[run_id] = (span, tokens)

    def on_llm_end(self, response: Any, *, run_id: Any = None, **kw: Any) -> None:
        entry = self._spans.pop(run_id, None)
        if not entry:
            return
        span, tokens = entry
        usage = getattr(response, "llm_output", None) or {}
        if isinstance(usage, dict) and "token_usage" in usage:
            span.set_attribute("token_usage", usage["token_usage"])
        span.set_output(str(response)[:2000])
        self._client().tracer.end_span(span, tokens)

    def on_llm_error(self, error: BaseException, *, run_id: Any = None, **kw: Any) -> None:
        self._finish_error(run_id, error)

    # --- tools -------------------------------------------------------------

    def on_tool_start(self, serialized: dict, input_str: str, *, run_id: Any = None, **kw: Any) -> None:
        name = (serialized or {}).get("name", "tool")
        span, tokens = self._client().tracer.start_span(name, kind="tool", tool=name)
        span.set_input(input_str)
        self._spans[run_id] = (span, tokens)

    def on_tool_end(self, output: str, *, run_id: Any = None, **kw: Any) -> None:
        entry = self._spans.pop(run_id, None)
        if not entry:
            return
        span, tokens = entry
        span.set_output(str(output)[:2000])
        self._client().tracer.end_span(span, tokens)

    def on_tool_error(self, error: BaseException, *, run_id: Any = None, **kw: Any) -> None:
        self._finish_error(run_id, error)

    # --- shared ------------------------------------------------------------

    def _finish_error(self, run_id: Any, error: BaseException) -> None:
        entry = self._spans.pop(run_id, None)
        if not entry:
            return
        span, tokens = entry
        span.record_error(error)
        self._client().tracer.end_span(span, tokens)
