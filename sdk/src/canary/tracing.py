"""Span + context model for Canary traces.

A *run* is the root span for one agent invocation. Inside it live child spans:
LLM calls, tool invocations, and generic spans. Every span records timing,
status, structured attributes, input/output, and — when it fails — the captured
exception. Spans are emitted to the configured transport as they finish, so the
backend can rebuild the tree from ``run_id``/``parent_id``.

Context is tracked with :mod:`contextvars`, which is coroutine- and
thread-safe, so nested ``@trace``/``span()`` usage works under asyncio too. If
``opentelemetry-api`` is installed we also read its current span so Canary spans
slot under an existing OTel trace when there is one.
"""

from __future__ import annotations

import time
import traceback
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .fingerprint import fingerprint

# Optional OpenTelemetry bridge — soft import, never a hard dependency.
try:  # pragma: no cover - exercised only when otel is installed
    from opentelemetry import trace as _otel_trace
except Exception:  # noqa: BLE001
    _otel_trace = None


def _new_id() -> str:
    """Short, collision-safe id for runs and spans."""
    return uuid.uuid4().hex


def _otel_context() -> tuple[Optional[str], Optional[str]]:
    """Return ``(trace_id, span_id)`` from the active OTel span, if any."""
    if _otel_trace is None:
        return None, None
    span = _otel_trace.get_current_span()
    ctx = getattr(span, "get_span_context", lambda: None)()
    if not ctx or not getattr(ctx, "is_valid", False):
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


@dataclass
class Span:
    """A single node in a run's trace tree."""

    name: str
    run_id: str
    kind: str = "span"  # one of: run | llm | tool | span
    span_id: str = field(default_factory=_new_id)
    parent_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "ok"  # ok | error
    attributes: dict[str, Any] = field(default_factory=dict)
    input: Any = None
    output: Any = None
    error: Optional[dict[str, Any]] = None
    otel_trace_id: Optional[str] = None
    otel_span_id: Optional[str] = None

    # --- fluent helpers used inside `with canary.span(...) as span:` ---------

    def set_input(self, value: Any) -> "Span":
        self.input = value
        return self

    def set_output(self, value: Any) -> "Span":
        self.output = value
        return self

    def set_attribute(self, key: str, value: Any) -> "Span":
        self.attributes[key] = value
        return self

    def record_error(self, exc: BaseException) -> "Span":
        """Attach a captured exception (type, message, traceback) to the span."""
        self.status = "error"
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # The frame where the error surfaced — used as the "failed at" step.
        failed_at = self.name
        tb_frames = traceback.extract_tb(exc.__traceback__)
        if tb_frames:
            last = tb_frames[-1]
            failed_at = f"{last.name} ({last.filename}:{last.lineno})"
        self.error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb,
            "failed_at": failed_at,
            # Fingerprint here so capture and query agree on grouping.
            "fingerprint": fingerprint(
                type(exc).__name__,
                tool=self.attributes.get("tool"),
                agent=self.attributes.get("agent"),
                message=str(exc),
            ),
        }
        return self

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time) * 1000, 3)

    def to_event(self) -> dict[str, Any]:
        """Serialise to the wire shape the backend ingests."""
        return {
            "span_id": self.span_id,
            "run_id": self.run_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
            "input": _truncate(self.input),
            "output": _truncate(self.output),
            "error": self.error,
            "otel_trace_id": self.otel_trace_id,
            "otel_span_id": self.otel_span_id,
        }


def _truncate(value: Any, limit: int = 8192) -> Any:
    """Keep payloads bounded so a giant prompt can't bloat the store."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"...<truncated {len(value) - limit} chars>"
    return value


# Currently-active span, propagated across await points and threads.
_current_span: ContextVar[Optional[Span]] = ContextVar("canary_current_span", default=None)
# Root run for the active context.
_current_run: ContextVar[Optional[Span]] = ContextVar("canary_current_run", default=None)


class Tracer:
    """Creates spans, threads context, and emits finished spans.

    The client injects an ``emit`` callback that forwards each finished span to
    the transport. Thought→action→observation steps are buffered on the run and
    flushed with it.
    """

    def __init__(self, emit: Callable[[dict[str, Any]], None], *, service: str = "default") -> None:
        self._emit = emit
        self.service = service

    # --- lifecycle ----------------------------------------------------------
    #
    # Construction and context-var mutation are separated: ``start_run`` /
    # ``start_span`` build the span AND enter it (returning the reset tokens),
    # while the ``@trace`` decorator and ``span()`` context manager in
    # ``client.py`` own the matching ``exit_*`` on the way out. This keeps the
    # active-span stack correct across nested and async usage.

    def start_run(self, name: str, *, task: Any = None, **attributes: Any) -> tuple[Span, tuple[Token, Token]]:
        trace_id, parent_span_id = _otel_context()
        run = Span(
            name=name,
            run_id=_new_id(),
            kind="run",
            attributes={"agent": name, "service": self.service, **attributes},
            input=task,
            otel_trace_id=trace_id,
            otel_span_id=parent_span_id,
        )
        run.attributes.setdefault("thoughts", [])
        run_token = _current_run.set(run)
        span_token = _current_span.set(run)
        # Tokens are always returned as (span_token, run_token) so end_span can
        # unpack them uniformly regardless of whether this was a run or a span.
        return run, (span_token, run_token)

    def start_span(
        self, name: str, *, kind: str = "span", **attributes: Any
    ) -> tuple[Span, tuple[Token, Optional[Token]]]:
        run = _current_run.get()
        parent = _current_span.get()
        # If there is no active run, this span becomes its own lightweight run.
        if run is None:
            return self.start_run(name, **attributes)
        span = Span(
            name=name,
            run_id=run.run_id,
            kind=kind,
            parent_id=parent.span_id if parent else run.span_id,
            attributes=dict(attributes),
        )
        # Inherit agent so tool errors fingerprint against the right agent.
        span.attributes.setdefault("agent", run.attributes.get("agent"))
        span_token = _current_span.set(span)
        return span, (span_token, None)

    def end_span(self, span: Span, tokens: tuple[Token, Optional[Token]]) -> None:
        """Stamp the end time, restore context, and emit the span."""
        if span.end_time is None:
            span.end_time = time.time()
        # Propagate a child failure up to the run status before we leave it.
        if span.status == "error":
            run = _current_run.get()
            if run is not None and run is not span:
                run.status = "error"
        span_token, run_token = tokens
        try:
            _current_span.reset(span_token)
            if run_token is not None:
                _current_run.reset(run_token)
        except (ValueError, LookupError):  # pragma: no cover - context already gone
            pass
        self._emit(span.to_event())

    def record_thought(self, thought: str, action: str | None = None, observation: str | None = None) -> None:
        """Append a reasoning step to the active run's trace."""
        run = _current_run.get()
        if run is None:
            return
        run.attributes.setdefault("thoughts", []).append(
            {"thought": thought, "action": action, "observation": observation}
        )

    def current_span(self) -> Optional[Span]:
        return _current_span.get()

    def current_run(self) -> Optional[Span]:
        return _current_run.get()
