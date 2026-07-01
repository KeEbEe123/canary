"""Pydantic models for the Canary API.

These describe both what the SDK sends (``Event`` / ``EventBatch``) and what the
dashboard reads (runs, error groups, stats, alerts). The wire shape of an
``Event`` mirrors ``canary.tracing.Span.to_event`` in the SDK.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# --- ingest -----------------------------------------------------------------


class Event(BaseModel):
    """One finished span sent by the SDK."""

    span_id: str
    run_id: str
    parent_id: Optional[str] = None
    name: str
    kind: str = "span"  # run | llm | tool | span
    status: str = "ok"  # ok | error
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    input: Any = None
    output: Any = None
    error: Optional[dict[str, Any]] = None
    otel_trace_id: Optional[str] = None
    otel_span_id: Optional[str] = None


class EventBatch(BaseModel):
    """A batch of events posted to ``/v1/events``."""

    events: list[Event]
    service: str = "default"


class IngestResult(BaseModel):
    accepted: int
    alerts_fired: int = 0


# --- reads ------------------------------------------------------------------


class RunSummary(BaseModel):
    """One row in the runs list."""

    run_id: str
    agent: str
    service: str = "default"
    status: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    task: Any = None
    span_count: int = 0
    error_count: int = 0
    cost_usd: float = 0.0
    error_type: Optional[str] = None


class SpanOut(Event):
    """A span as returned inside a run's trace (same shape as ingest)."""


class RunDetail(BaseModel):
    """Full trace for one run."""

    run: RunSummary
    spans: list[SpanOut]
    thoughts: list[dict[str, Any]] = Field(default_factory=list)


class ErrorGroup(BaseModel):
    """A cluster of failures sharing a fingerprint."""

    fingerprint: str
    error_type: str
    sample_message: str
    tool: Optional[str] = None
    agent: Optional[str] = None
    count: int
    first_seen: float
    last_seen: float
    affected_agents: list[str] = Field(default_factory=list)
    affected_tools: list[str] = Field(default_factory=list)
    sample_run_id: Optional[str] = None


class TrendPoint(BaseModel):
    date: str
    runs: int
    errors: int


class NameCount(BaseModel):
    name: str
    total: int
    errors: int
    error_rate: float


class Stats(BaseModel):
    """Aggregate overview for the stats page."""

    total_runs: int
    success_rate: float
    error_rate: float
    avg_latency_ms: float
    total_cost_usd: float
    trend: list[TrendPoint] = Field(default_factory=list)
    top_failing_tools: list[NameCount] = Field(default_factory=list)
    top_failing_agents: list[NameCount] = Field(default_factory=list)


# --- alerts -----------------------------------------------------------------


class AlertScope(BaseModel):
    """What an alert rule watches. Empty scope == all traffic."""

    tool: Optional[str] = None
    agent: Optional[str] = None


class AlertRuleCreate(BaseModel):
    """Payload for creating an alert rule."""

    name: str
    # e.g. "failure_rate > 0.3" or "error_count > 10"
    condition: str
    scope: AlertScope = Field(default_factory=AlertScope)
    window_minutes: int = 60
    channel: str = "webhook"  # webhook | log
    webhook_url: Optional[str] = None
    enabled: bool = True


class AlertRule(AlertRuleCreate):
    id: str
    created_at: float


class AlertFiring(BaseModel):
    id: str
    rule_id: str
    rule_name: str
    fired_at: float
    value: float
    message: str


class AlertsResponse(BaseModel):
    rules: list[AlertRule]
    recent_firings: list[AlertFiring]
