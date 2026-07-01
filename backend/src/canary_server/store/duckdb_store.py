"""DuckDB-backed event store — the zero-config local default.

One embedded DuckDB file, no server, no Docker. Spans land in a single wide
``spans`` table with a few hot fields (agent, tool, model, cost, fingerprint,
error type/message) denormalised out of the JSON payload at write time so runs,
error groups, and stats are all cheap SQL. A process-wide lock serialises access
because a DuckDB connection is not safe for concurrent use.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Optional

import duckdb

from ..fingerprint import fingerprint as compute_fingerprint
from ..models import (
    AlertFiring,
    AlertRule,
    AlertRuleCreate,
    ErrorGroup,
    NameCount,
    RunDetail,
    RunSummary,
    SpanOut,
    Stats,
    TrendPoint,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS spans (
    span_id       VARCHAR PRIMARY KEY,
    run_id        VARCHAR,
    parent_id     VARCHAR,
    name          VARCHAR,
    kind          VARCHAR,
    status        VARCHAR,
    start_time    DOUBLE,
    end_time      DOUBLE,
    duration_ms   DOUBLE,
    service       VARCHAR,
    agent         VARCHAR,
    tool          VARCHAR,
    model         VARCHAR,
    cost_usd      DOUBLE DEFAULT 0,
    fingerprint   VARCHAR,
    error_type    VARCHAR,
    error_message VARCHAR,
    attributes    JSON,
    input         JSON,
    output        JSON,
    error         JSON
);
CREATE INDEX IF NOT EXISTS idx_spans_run ON spans(run_id);
CREATE INDEX IF NOT EXISTS idx_spans_fp ON spans(fingerprint);
CREATE INDEX IF NOT EXISTS idx_spans_start ON spans(start_time);

CREATE TABLE IF NOT EXISTS alert_rules (
    id            VARCHAR PRIMARY KEY,
    name          VARCHAR,
    condition     VARCHAR,
    scope_tool    VARCHAR,
    scope_agent   VARCHAR,
    window_minutes INTEGER,
    channel       VARCHAR,
    webhook_url   VARCHAR,
    enabled       BOOLEAN,
    created_at    DOUBLE
);

CREATE TABLE IF NOT EXISTS alert_firings (
    id         VARCHAR PRIMARY KEY,
    rule_id    VARCHAR,
    rule_name  VARCHAR,
    fired_at   DOUBLE,
    value      DOUBLE,
    message    VARCHAR
);
"""


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _loads(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


class DuckDBStore:
    """Concrete :class:`EventStore` on top of DuckDB."""

    def __init__(self, db_path: str = ":memory:") -> None:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # Multiple app threads (uvicorn workers, the SDK's DirectTransport)
        # share this connection, so guard every call with a reentrant lock.
        self._lock = threading.RLock()
        self._conn = duckdb.connect(db_path)
        self._conn.execute(_SCHEMA)

    # --- ingest ------------------------------------------------------------

    def write_events(self, events: list[dict[str, Any]]) -> int:
        rows = [self._to_row(e) for e in events]
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                """INSERT OR REPLACE INTO spans (
                    span_id, run_id, parent_id, name, kind, status,
                    start_time, end_time, duration_ms, service, agent, tool,
                    model, cost_usd, fingerprint, error_type, error_message,
                    attributes, input, output, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    def _to_row(self, e: dict[str, Any]) -> list[Any]:
        """Flatten an event into a spans row, denormalising hot fields."""
        attrs = e.get("attributes") or {}
        error = e.get("error") or None
        tool = attrs.get("tool")
        agent = attrs.get("agent")
        # Recompute the fingerprint here if the SDK didn't attach one, so
        # server-side grouping never depends on client cooperation.
        fp = None
        err_type = err_msg = None
        if error:
            err_type = error.get("type")
            err_msg = error.get("message")
            fp = error.get("fingerprint") or compute_fingerprint(
                err_type, tool=tool, agent=agent, message=err_msg
            )
        return [
            e["span_id"],
            e["run_id"],
            e.get("parent_id"),
            e.get("name"),
            e.get("kind", "span"),
            e.get("status", "ok"),
            e.get("start_time"),
            e.get("end_time"),
            e.get("duration_ms"),
            attrs.get("service", e.get("service", "default")),
            agent,
            tool,
            attrs.get("model"),
            float(attrs.get("cost_usd") or 0.0),
            fp,
            err_type,
            err_msg,
            _dumps(attrs),
            _dumps(e.get("input")),
            _dumps(e.get("output")),
            _dumps(error),
        ]

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
        where = ["r.kind = 'run'"]
        params: list[Any] = []
        for column, value in (("r.agent", agent), ("r.status", status), ("r.service", service)):
            if value is not None:
                where.append(f"{column} = ?")
                params.append(value)
        if start is not None:
            where.append("r.start_time >= ?")
            params.append(start)
        if end is not None:
            where.append("r.start_time <= ?")
            params.append(end)
        sql = f"""
            SELECT r.run_id, r.agent, r.service, r.status, r.start_time, r.end_time,
                   r.duration_ms, r.input,
                   (SELECT count(*) FROM spans s WHERE s.run_id = r.run_id) AS span_count,
                   (SELECT count(*) FROM spans s WHERE s.run_id = r.run_id AND s.error IS NOT NULL) AS error_count,
                   (SELECT coalesce(sum(cost_usd), 0) FROM spans s WHERE s.run_id = r.run_id) AS cost_usd,
                   coalesce(r.error_type, (
                       SELECT s.error_type FROM spans s
                       WHERE s.run_id = r.run_id AND s.error_type IS NOT NULL
                       ORDER BY s.start_time LIMIT 1)) AS error_type
            FROM spans r
            WHERE {' AND '.join(where)}
            ORDER BY r.start_time DESC
            LIMIT ? OFFSET ?
        """
        params += [limit, offset]
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            RunSummary(
                run_id=row[0],
                agent=row[1] or "unknown",
                service=row[2] or "default",
                status=row[3] or "ok",
                start_time=row[4],
                end_time=row[5],
                duration_ms=row[6],
                task=_loads(row[7]),
                span_count=row[8],
                error_count=row[9],
                cost_usd=round(row[10] or 0.0, 6),
                error_type=row[11],
            )
            for row in rows
        ]

    def get_run(self, run_id: str) -> Optional[RunDetail]:
        with self._lock:
            span_rows = self._conn.execute(
                "SELECT * FROM spans WHERE run_id = ? ORDER BY start_time", [run_id]
            ).fetchall()
            columns = [d[0] for d in self._conn.description]
        if not span_rows:
            return None
        spans = [self._row_to_span(dict(zip(columns, row))) for row in span_rows]
        root = next((s for s in spans if s.kind == "run"), spans[0])
        thoughts = (root.attributes or {}).get("thoughts", []) if root.attributes else []
        summary = RunSummary(
            run_id=run_id,
            agent=root.attributes.get("agent", "unknown") if root.attributes else "unknown",
            service=root.attributes.get("service", "default") if root.attributes else "default",
            status="error" if any(s.status == "error" for s in spans) else root.status,
            start_time=root.start_time,
            end_time=root.end_time,
            duration_ms=root.duration_ms,
            task=root.input,
            span_count=len(spans),
            error_count=sum(1 for s in spans if s.error is not None),
            cost_usd=round(sum((s.attributes or {}).get("cost_usd", 0) or 0 for s in spans), 6),
            error_type=next((s.error["type"] for s in spans if s.error), None),
        )
        return RunDetail(run=summary, spans=spans, thoughts=thoughts)

    def _row_to_span(self, r: dict[str, Any]) -> SpanOut:
        return SpanOut(
            span_id=r["span_id"],
            run_id=r["run_id"],
            parent_id=r["parent_id"],
            name=r["name"],
            kind=r["kind"],
            status=r["status"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            duration_ms=r["duration_ms"],
            attributes=_loads(r["attributes"]) or {},
            input=_loads(r["input"]),
            output=_loads(r["output"]),
            error=_loads(r["error"]),
        )

    # --- errors ------------------------------------------------------------

    def list_error_groups(
        self,
        *,
        agent: Optional[str] = None,
        tool: Optional[str] = None,
        limit: int = 50,
    ) -> list[ErrorGroup]:
        where = ["status = 'error'", "fingerprint IS NOT NULL"]
        params: list[Any] = []
        if agent is not None:
            where.append("agent = ?")
            params.append(agent)
        if tool is not None:
            where.append("tool = ?")
            params.append(tool)
        sql = f"""
            SELECT fingerprint,
                   any_value(error_type)    AS error_type,
                   any_value(error_message) AS sample_message,
                   any_value(tool)          AS tool,
                   any_value(agent)         AS agent,
                   count(*)                 AS cnt,
                   min(start_time)          AS first_seen,
                   max(start_time)          AS last_seen,
                   list(DISTINCT agent)     AS agents,
                   list(DISTINCT tool)      AS tools,
                   any_value(run_id)        AS sample_run
            FROM spans
            WHERE {' AND '.join(where)}
            GROUP BY fingerprint
            ORDER BY last_seen DESC
            LIMIT ?
        """
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        groups = []
        for row in rows:
            groups.append(
                ErrorGroup(
                    fingerprint=row[0],
                    error_type=row[1] or "UnknownError",
                    sample_message=row[2] or "",
                    tool=row[3],
                    agent=row[4],
                    count=row[5],
                    first_seen=row[6],
                    last_seen=row[7],
                    affected_agents=[a for a in (row[8] or []) if a],
                    affected_tools=[t for t in (row[9] or []) if t],
                    sample_run_id=row[10],
                )
            )
        return groups

    # --- stats -------------------------------------------------------------

    def stats(self, *, days: int = 7) -> Stats:
        with self._lock:
            total_runs, errored_runs, avg_latency = self._conn.execute(
                """SELECT count(*),
                          count(*) FILTER (WHERE status = 'error'),
                          coalesce(avg(duration_ms), 0)
                   FROM spans WHERE kind = 'run'"""
            ).fetchone()
            total_cost = self._conn.execute(
                "SELECT coalesce(sum(cost_usd), 0) FROM spans"
            ).fetchone()[0]
            since = time.time() - days * 86400
            trend_rows = self._conn.execute(
                """SELECT strftime(to_timestamp(start_time), '%Y-%m-%d') AS day,
                          count(*),
                          count(*) FILTER (WHERE status = 'error')
                   FROM spans WHERE kind = 'run' AND start_time >= ?
                   GROUP BY day ORDER BY day""",
                [since],
            ).fetchall()
            tool_rows = self._conn.execute(
                """SELECT tool, count(*),
                          count(*) FILTER (WHERE status = 'error') AS errs
                   FROM spans WHERE kind = 'tool' AND tool IS NOT NULL
                   GROUP BY tool HAVING errs > 0 ORDER BY errs DESC LIMIT 5"""
            ).fetchall()
            agent_rows = self._conn.execute(
                """SELECT agent, count(*),
                          count(*) FILTER (WHERE status = 'error') AS errs
                   FROM spans WHERE kind = 'run' AND agent IS NOT NULL
                   GROUP BY agent HAVING errs > 0 ORDER BY errs DESC LIMIT 5"""
            ).fetchall()

        total_runs = total_runs or 0
        errored_runs = errored_runs or 0
        error_rate = round(errored_runs / total_runs, 4) if total_runs else 0.0
        return Stats(
            total_runs=total_runs,
            success_rate=round(1 - error_rate, 4),
            error_rate=error_rate,
            avg_latency_ms=round(avg_latency or 0.0, 2),
            total_cost_usd=round(total_cost or 0.0, 6),
            trend=[TrendPoint(date=r[0], runs=r[1], errors=r[2]) for r in trend_rows],
            top_failing_tools=[self._name_count(r) for r in tool_rows],
            top_failing_agents=[self._name_count(r) for r in agent_rows],
        )

    @staticmethod
    def _name_count(row: tuple[Any, ...]) -> NameCount:
        name, total, errors = row
        return NameCount(
            name=name,
            total=total,
            errors=errors,
            error_rate=round(errors / total, 4) if total else 0.0,
        )

    # --- alerts ------------------------------------------------------------

    def create_alert_rule(self, rule: AlertRuleCreate) -> AlertRule:
        import uuid

        created = AlertRule(id=uuid.uuid4().hex, created_at=time.time(), **rule.model_dump())
        with self._lock:
            self._conn.execute(
                """INSERT INTO alert_rules (id, name, condition, scope_tool, scope_agent,
                       window_minutes, channel, webhook_url, enabled, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    created.id, created.name, created.condition,
                    created.scope.tool, created.scope.agent, created.window_minutes,
                    created.channel, created.webhook_url, created.enabled, created.created_at,
                ],
            )
        return created

    def list_alert_rules(self) -> list[AlertRule]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, name, condition, scope_tool, scope_agent, window_minutes,
                          channel, webhook_url, enabled, created_at
                   FROM alert_rules ORDER BY created_at DESC"""
            ).fetchall()
        return [
            AlertRule(
                id=r[0], name=r[1], condition=r[2],
                scope={"tool": r[3], "agent": r[4]},
                window_minutes=r[5], channel=r[6], webhook_url=r[7],
                enabled=r[8], created_at=r[9],
            )
            for r in rows
        ]

    def list_alert_firings(self, *, limit: int = 50) -> list[AlertFiring]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, rule_id, rule_name, fired_at, value, message
                   FROM alert_firings ORDER BY fired_at DESC LIMIT ?""",
                [limit],
            ).fetchall()
        return [
            AlertFiring(id=r[0], rule_id=r[1], rule_name=r[2], fired_at=r[3], value=r[4], message=r[5])
            for r in rows
        ]

    def record_firing(self, rule: AlertRule, value: float, message: str) -> AlertFiring:
        import uuid

        firing = AlertFiring(
            id=uuid.uuid4().hex, rule_id=rule.id, rule_name=rule.name,
            fired_at=time.time(), value=value, message=message,
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO alert_firings (id, rule_id, rule_name, fired_at, value, message) VALUES (?, ?, ?, ?, ?, ?)",
                [firing.id, firing.rule_id, firing.rule_name, firing.fired_at, firing.value, firing.message],
            )
        return firing

    def scope_metrics(
        self,
        *,
        tool: Optional[str] = None,
        agent: Optional[str] = None,
        window_minutes: int = 60,
    ) -> dict[str, float]:
        since = time.time() - window_minutes * 60
        if tool:
            where, params = "kind = 'tool' AND tool = ?", [tool]
        elif agent:
            where, params = "kind = 'run' AND agent = ?", [agent]
        else:
            where, params = "kind = 'run'", []
        with self._lock:
            total, errors = self._conn.execute(
                f"""SELECT count(*), count(*) FILTER (WHERE status = 'error')
                    FROM spans WHERE {where} AND start_time >= ?""",
                params + [since],
            ).fetchone()
        total = total or 0
        errors = errors or 0
        return {
            "total": float(total),
            "errors": float(errors),
            "failure_rate": round(errors / total, 4) if total else 0.0,
        }
