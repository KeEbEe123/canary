"""Public Canary API: ``init``, ``trace``, ``span``, ``instrument``.

This is the surface users touch. Three lines get you tracking::

    import canary
    canary.init()                 # local mode: DuckDB + dashboard on :8732

    @canary.trace("my_agent")
    def run_agent(task): ...

Everything routes through a process-global :class:`CanaryClient` created by
``init()``. Runs are buffered per-``run_id`` and flushed when the root run
finishes, which lets us sample cleanly while *always* keeping runs that failed.
"""

from __future__ import annotations

import atexit
import functools
import inspect
import random
import threading
from typing import Any, Awaitable, Callable, Optional, TypeVar

from .config import CanaryConfig
from .tracing import Span, Tracer
from .transport import NoopTransport, Transport

F = TypeVar("F", bound=Callable[..., Any])


class CanaryClient:
    """Owns config, the tracer, and the transport for one process."""

    def __init__(self, config: CanaryConfig, transport: Transport) -> None:
        self.config = config
        self.transport = transport
        self.tracer = Tracer(self._emit_span, service=config.service)
        # Per-run buffers so sampling can decide keep/drop atomically at run end.
        self._buffers: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # --- span emission + sampling ------------------------------------------

    def _emit_span(self, event: dict[str, Any]) -> None:
        run_id = event["run_id"]
        with self._lock:
            self._buffers.setdefault(run_id, []).append(event)
            if event["kind"] != "run":
                return  # buffer children; flush when the root run closes
            batch = self._buffers.pop(run_id, [])
        # Keep everything that errored; otherwise honour the sample rate.
        errored = any(e["status"] == "error" for e in batch)
        if errored or random.random() < self.config.sample_rate:
            for e in batch:
                self.transport.emit(e)

    # --- lifecycle ----------------------------------------------------------

    def flush(self) -> None:
        self.transport.flush()

    def shutdown(self) -> None:
        # Emit any runs still open (best effort), then close the transport.
        with self._lock:
            leftovers = list(self._buffers.values())
            self._buffers.clear()
        for batch in leftovers:
            for e in batch:
                self.transport.emit(e)
        self.transport.shutdown()


# --- process-global client --------------------------------------------------

_client: Optional[CanaryClient] = None
_client_lock = threading.Lock()


def init(**kwargs: Any) -> CanaryClient:
    """Initialise Canary. Call once at startup.

    With no arguments this starts *local* mode: an in-process DuckDB store plus
    the dashboard on ``http://localhost:8732``. Pass ``api_key=...`` (and
    optionally ``endpoint=...``) to ship traces to a remote collector instead.
    """
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        config = CanaryConfig.resolve(**kwargs)
        transport = _build_transport(config)
        _client = CanaryClient(config, transport)
        atexit.register(_client.shutdown)
        return _client


def _build_transport(config: CanaryConfig) -> Transport:
    """Construct the transport, booting the local server when in local mode."""
    if config.is_local:
        # Imported lazily so production installs need not pull the server in.
        from .local_server import start_local_server

        store = start_local_server(config)
        from .transport import DirectTransport

        return DirectTransport(store)
    from .transport import HTTPTransport

    return HTTPTransport(config)


def _require_client() -> CanaryClient:
    """Return the client, auto-initialising local mode if the user forgot."""
    if _client is None:
        return init()
    return _client


# --- public decorators / context managers -----------------------------------


def trace(name: str | Callable[..., Any] | None = None, **run_attrs: Any) -> Any:
    """Trace a function as one agent run.

    Usable as ``@trace`` or ``@trace("agent_name", team="growth")``. Captures
    the return value as the run output and any raised exception (type, message,
    traceback, failing step) as the run error, then re-raises. Works on both
    sync and async functions.
    """

    def decorate(func: F) -> F:
        run_name = name if isinstance(name, str) else func.__name__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                client = _require_client()
                task = _first_arg(args, kwargs)
                run, tokens = client.tracer.start_run(run_name, task=task, **run_attrs)
                try:
                    result = await func(*args, **kwargs)
                    run.set_output(result)
                    return result
                except BaseException as exc:  # noqa: BLE001 - re-raised below
                    # If a child span already captured this failure, don't
                    # double-count it as a second error group at the run level.
                    if run.status != "error":
                        run.record_error(exc)
                    raise
                finally:
                    client.tracer.end_span(run, tokens)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            client = _require_client()
            task = _first_arg(args, kwargs)
            run, tokens = client.tracer.start_run(run_name, task=task, **run_attrs)
            try:
                result = func(*args, **kwargs)
                run.set_output(result)
                return result
            except BaseException as exc:  # noqa: BLE001 - re-raised below
                # If a child span already captured this failure, don't
                # double-count it as a second error group at the run level.
                if run.status != "error":
                    run.record_error(exc)
                raise
            finally:
                client.tracer.end_span(run, tokens)

        return sync_wrapper  # type: ignore[return-value]

    # Bare @trace (no parentheses) passes the function straight in.
    if callable(name):
        return decorate(name)
    return decorate


class _SpanContext:
    """Context manager returned by :func:`span`; supports sync and async ``with``."""

    def __init__(self, name: str, kind: str, attributes: dict[str, Any]) -> None:
        self._name = name
        self._kind = kind
        self._attributes = attributes
        self._span: Optional[Span] = None
        self._tokens: Any = None

    def _enter(self) -> Span:
        client = _require_client()
        self._span, self._tokens = client.tracer.start_span(
            self._name, kind=self._kind, **self._attributes
        )
        return self._span

    def _exit(self, exc: BaseException | None) -> None:
        client = _require_client()
        if self._span is not None:
            if exc is not None:
                self._span.record_error(exc)
            client.tracer.end_span(self._span, self._tokens)

    def __enter__(self) -> Span:
        return self._enter()

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        self._exit(exc)
        return False  # never suppress the exception

    async def __aenter__(self) -> Span:
        return self._enter()

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        self._exit(exc)
        return False


def span(name: str, *, kind: str = "span", **attributes: Any) -> _SpanContext:
    """Open a manual span::

        with canary.span("tool_call", kind="tool", tool="search") as s:
            s.set_output(search(q))
    """
    return _SpanContext(name, kind, attributes)


def record(thought: str, action: str | None = None, observation: str | None = None) -> None:
    """Append a thought→action→observation step to the current run."""
    _require_client().tracer.record_thought(thought, action, observation)


def instrument(library: str) -> None:
    """Auto-instrument a supported library (``"openai"`` or ``"langchain"``)."""
    _require_client()  # ensure a client exists first
    if library == "openai":
        from .instrumentation.openai import instrument_openai

        instrument_openai()
    elif library == "langchain":
        from .instrumentation.langchain import CanaryCallbackHandler  # noqa: F401

        # LangChain is wired by passing the handler; nothing global to patch.
    else:
        raise ValueError(f"unknown instrumentation target: {library!r}")


def flush() -> None:
    """Flush buffered spans to the transport."""
    if _client is not None:
        _client.flush()


def shutdown() -> None:
    """Flush and tear down the client (also runs automatically at exit)."""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None


def get_client() -> Optional[CanaryClient]:
    """Return the active client (or ``None`` if uninitialised). Used in tests."""
    return _client


def _first_arg(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    """Best-effort capture of the 'task' — the first positional or kw arg."""
    if args:
        return args[0]
    if kwargs:
        return next(iter(kwargs.values()))
    return None
