"""The ``EventStore`` protocol — the single seam between the API and storage.

Every backend (DuckDB, ClickHouse, or a future one) implements these methods.
Routes depend only on this protocol, so swapping storage never touches the API
layer. Methods return the pydantic models from :mod:`canary_server.models`.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from ..models import (
    AlertFiring,
    AlertRule,
    AlertRuleCreate,
    ErrorGroup,
    RunDetail,
    RunSummary,
    Stats,
)


@runtime_checkable
class EventStore(Protocol):
    """Persistence + query surface for spans, errors, stats, and alerts."""

    # --- ingest ------------------------------------------------------------

    def write_events(self, events: list[dict[str, Any]]) -> int:
        """Persist a batch of span events. Returns the number written."""
        ...

    # --- runs --------------------------------------------------------------

    def list_runs(
        self,
        *,
        agent: Optional[str] = None,
        status: Optional[str] = None,
        service: Optional[str] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RunSummary]:
        """List run summaries newest-first, filtered as given."""
        ...

    def get_run(self, run_id: str) -> Optional[RunDetail]:
        """Full trace (all spans + thoughts) for one run, or ``None``."""
        ...

    # --- errors ------------------------------------------------------------

    def list_error_groups(
        self,
        *,
        agent: Optional[str] = None,
        tool: Optional[str] = None,
        limit: int = 50,
    ) -> list[ErrorGroup]:
        """Failures clustered by fingerprint, most recent first."""
        ...

    # --- stats -------------------------------------------------------------

    def stats(self, *, days: int = 7) -> Stats:
        """Aggregate overview over the trailing ``days`` window."""
        ...

    # --- alerts ------------------------------------------------------------

    def create_alert_rule(self, rule: AlertRuleCreate) -> AlertRule:
        ...

    def list_alert_rules(self) -> list[AlertRule]:
        ...

    def list_alert_firings(self, *, limit: int = 50) -> list[AlertFiring]:
        ...

    def record_firing(self, rule: AlertRule, value: float, message: str) -> AlertFiring:
        ...

    def scope_metrics(
        self,
        *,
        tool: Optional[str] = None,
        agent: Optional[str] = None,
        window_minutes: int = 60,
    ) -> dict[str, float]:
        """Return ``{total, errors, failure_rate}`` for a scope over a window."""
        ...
