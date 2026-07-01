"""Tests for the DuckDB store: write/query, error grouping, stats."""

from __future__ import annotations

import time

import pytest

from canary_server.fingerprint import fingerprint
from canary_server.store.duckdb_store import DuckDBStore


@pytest.fixture
def store() -> DuckDBStore:
    return DuckDBStore(":memory:")


def _run_events(run_id: str, agent: str, *, start: float, tool_error=None):
    """Build a run span plus one tool span (optionally failing)."""
    run = {
        "span_id": f"{run_id}-root", "run_id": run_id, "parent_id": None, "name": agent,
        "kind": "run", "status": "ok", "start_time": start, "end_time": start + 1,
        "duration_ms": 1000.0, "attributes": {"agent": agent, "service": "test"},
        "input": "task", "output": None, "error": None,
    }
    tool = {
        "span_id": f"{run_id}-t", "run_id": run_id, "parent_id": f"{run_id}-root",
        "name": "search", "kind": "tool", "status": "ok", "start_time": start,
        "end_time": start + 0.5, "duration_ms": 500.0,
        "attributes": {"agent": agent, "tool": "search"}, "input": None, "output": "ok", "error": None,
    }
    if tool_error:
        etype, msg = tool_error
        tool["status"] = "error"
        tool["error"] = {
            "type": etype, "message": msg, "traceback": f"{etype}: {msg}",
            "failed_at": "search (t.py:1)",
            "fingerprint": fingerprint(etype, tool="search", agent=agent, message=msg),
        }
        run["status"] = "error"
    return [run, tool]


def test_write_and_list_runs(store: DuckDBStore):
    now = time.time()
    store.write_events(_run_events("r1", "agent_a", start=now))
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0].agent == "agent_a"
    assert runs[0].span_count == 2
    assert runs[0].status == "ok"


def test_run_detail_returns_full_tree(store: DuckDBStore):
    now = time.time()
    store.write_events(_run_events("r1", "agent_a", start=now, tool_error=("ValueError", "bad x")))
    detail = store.get_run("r1")
    assert detail is not None
    assert detail.run.status == "error"
    assert detail.run.error_count == 1
    assert {s.kind for s in detail.spans} == {"run", "tool"}


def test_get_missing_run_returns_none(store: DuckDBStore):
    assert store.get_run("nope") is None


def test_error_grouping_by_fingerprint(store: DuckDBStore):
    now = time.time()
    # Same exception type + tool + agent, different message details -> ONE group.
    store.write_events(_run_events("r1", "agent_a", start=now, tool_error=("TimeoutError", "timed out after 12ms")))
    store.write_events(_run_events("r2", "agent_a", start=now, tool_error=("TimeoutError", "timed out after 999ms")))
    # Different agent -> a separate group.
    store.write_events(_run_events("r3", "agent_b", start=now, tool_error=("TimeoutError", "timed out after 5ms")))

    groups = store.list_error_groups()
    assert len(groups) == 2
    top = next(g for g in groups if g.agent == "agent_a")
    assert top.count == 2
    assert top.error_type == "TimeoutError"
    assert top.tool == "search"


def test_stats_aggregates(store: DuckDBStore):
    now = time.time()
    store.write_events(_run_events("r1", "agent_a", start=now))
    store.write_events(_run_events("r2", "agent_a", start=now, tool_error=("ValueError", "boom")))
    stats = store.stats()
    assert stats.total_runs == 2
    assert stats.error_rate == pytest.approx(0.5)
    assert stats.success_rate == pytest.approx(0.5)
    assert any(t.name == "search" for t in stats.top_failing_tools)
    assert len(stats.trend) >= 1


def test_scope_metrics_for_tool(store: DuckDBStore):
    now = time.time()
    store.write_events(_run_events("r1", "agent_a", start=now, tool_error=("ValueError", "boom")))
    store.write_events(_run_events("r2", "agent_a", start=now))
    m = store.scope_metrics(tool="search", window_minutes=60)
    assert m["total"] == 2
    assert m["errors"] == 1
    assert m["failure_rate"] == pytest.approx(0.5)
