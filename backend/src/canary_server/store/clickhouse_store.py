"""ClickHouse event store — production stub (v0.1).

DuckDB is perfect for local and small deployments but a single file won't scale
to millions of spans a day. For production, Canary targets ClickHouse: columnar,
append-optimised, and built for exactly this "high-cardinality events, aggregate
fast" workload.

This class implements the :class:`EventStore` protocol so it drops in wherever
``DuckDBStore`` is used (select it with ``CANARY_STORE=clickhouse``). The methods
are intentionally stubbed for v0.1 — the target schema lives in the docstrings
below so the port is a fill-in-the-blanks job, not a redesign.

Target schema::

    CREATE TABLE spans (
        span_id       String,
        run_id        String,
        parent_id     String,
        name          String,
        kind          LowCardinality(String),
        status        LowCardinality(String),
        start_time    DateTime64(6),
        end_time      Nullable(DateTime64(6)),
        duration_ms   Float64,
        service       LowCardinality(String),
        agent         LowCardinality(String),
        tool          LowCardinality(String),
        model         LowCardinality(String),
        cost_usd      Float64,
        fingerprint   String,
        error_type    String,
        error_message String,
        attributes    String,   -- JSON
        input         String,   -- JSON
        output        String,   -- JSON
        error         String    -- JSON
    ) ENGINE = MergeTree
    PARTITION BY toYYYYMMDD(start_time)
    ORDER BY (service, agent, start_time);

    -- error groups + stats are GROUP BY queries over `spans`;
    -- alert_rules / alert_firings can live in a small ReplacingMergeTree.
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import (
    AlertFiring,
    AlertRule,
    AlertRuleCreate,
    ErrorGroup,
    RunDetail,
    RunSummary,
    Stats,
)

_NOT_IMPLEMENTED = (
    "ClickHouseStore is a v0.1 stub. Use the DuckDB store (default) for now, or "
    "implement this against the schema documented in clickhouse_store.py. "
    "Install with: pip install 'canary-server[clickhouse]'."
)


class ClickHouseStore:
    """Production :class:`EventStore` backed by ClickHouse (not yet implemented)."""

    def __init__(self, dsn: str) -> None:
        # TODO: `import clickhouse_connect; self._client = clickhouse_connect.get_client(dsn=dsn)`
        #       then run the DDL above (idempotent CREATE TABLE IF NOT EXISTS).
        self._dsn = dsn

    def write_events(self, events: list[dict[str, Any]]) -> int:
        # TODO: batch INSERT via self._client.insert("spans", rows, column_names=...)
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_runs(self, **kwargs: Any) -> list[RunSummary]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def get_run(self, run_id: str) -> Optional[RunDetail]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_error_groups(self, **kwargs: Any) -> list[ErrorGroup]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def stats(self, *, days: int = 7) -> Stats:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def create_alert_rule(self, rule: AlertRuleCreate) -> AlertRule:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_alert_rules(self) -> list[AlertRule]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def list_alert_firings(self, *, limit: int = 50) -> list[AlertFiring]:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def record_firing(self, rule: AlertRule, value: float, message: str) -> AlertFiring:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def scope_metrics(self, **kwargs: Any) -> dict[str, float]:
        raise NotImplementedError(_NOT_IMPLEMENTED)
