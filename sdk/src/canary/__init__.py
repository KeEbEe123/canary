"""Canary — Sentry for AI agents. Error tracking, not analytics.

AI agents fail silently: a tool returns garbage, an LLM call times out, a loop
never terminates, an exception is swallowed three frames deep. Canary makes
those failures visible. Instrument your agent in three lines::

    import canary
    canary.init()

    @canary.trace("research_agent")
    def run(task: str):
        with canary.span("search", kind="tool", tool="web_search") as s:
            s.set_output(web_search(task))
        ...

Local mode (the default) boots a DuckDB store and a dashboard on
``http://localhost:8732``. Production mode ships batched traces to a remote
collector: ``canary.init(api_key="...", endpoint="https://api.canary.dev")``.
"""

from __future__ import annotations

from .client import (
    CanaryClient,
    flush,
    get_client,
    init,
    instrument,
    record,
    shutdown,
    span,
    trace,
)
from .config import CanaryConfig, Mode
from .fingerprint import fingerprint, normalize_message
from .tracing import Span

__version__ = "0.1.0"

__all__ = [
    "CanaryClient",
    "CanaryConfig",
    "Mode",
    "Span",
    "__version__",
    "fingerprint",
    "flush",
    "get_client",
    "init",
    "instrument",
    "normalize_message",
    "record",
    "shutdown",
    "span",
    "trace",
]
