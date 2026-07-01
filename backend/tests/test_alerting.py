"""Tests for alert rule parsing, evaluation, scope, firing, and cooldown."""

from __future__ import annotations

import time

import pytest

from canary_server.alerting import ConditionError, evaluate_rules, parse_condition
from canary_server.models import AlertRuleCreate
from canary_server.store.duckdb_store import DuckDBStore


def _failing_tool_run(run_id: str, agent="agent_a", tool="search"):
    now = time.time()
    return [
        {"span_id": f"{run_id}-r", "run_id": run_id, "name": agent, "kind": "run",
         "status": "error", "start_time": now, "attributes": {"agent": agent, "service": "t"}},
        {"span_id": f"{run_id}-t", "run_id": run_id, "parent_id": f"{run_id}-r", "name": tool,
         "kind": "tool", "status": "error", "start_time": now,
         "attributes": {"agent": agent, "tool": tool},
         "error": {"type": "TimeoutError", "message": "boom", "fingerprint": "abc123def4567890"}},
    ]


# --- parsing ---------------------------------------------------------------


def test_parse_condition_valid():
    assert parse_condition("failure_rate > 0.3") == ("failure_rate", ">", 0.3)
    assert parse_condition("error_count >= 10") == ("error_count", ">=", 10.0)


@pytest.mark.parametrize("bad", ["failure_rate", "boom > 1", "failure_rate ! 1", "> 0.3", "__import__('os')"])
def test_parse_condition_rejects_garbage(bad):
    with pytest.raises(ConditionError):
        parse_condition(bad)


# --- evaluation ------------------------------------------------------------


def test_rule_fires_when_threshold_crossed():
    store = DuckDBStore(":memory:")
    store.write_events(_failing_tool_run("r1"))
    store.create_alert_rule(
        AlertRuleCreate(
            name="search failing", condition="failure_rate > 0.3",
            scope={"tool": "search"}, window_minutes=60, channel="log",
        )
    )
    fired = evaluate_rules(store)
    assert len(fired) == 1
    assert "search failing" in fired[0].message
    # And it's persisted.
    assert len(store.list_alert_firings()) == 1


def test_rule_does_not_fire_below_threshold():
    store = DuckDBStore(":memory:")
    # One failing + one ok tool span -> 50% within scope; threshold 0.9 not met.
    store.write_events(_failing_tool_run("r1"))
    store.write_events(
        [{"span_id": "ok-t", "run_id": "r2", "name": "search", "kind": "tool", "status": "ok",
          "start_time": time.time(), "attributes": {"agent": "agent_a", "tool": "search"}}]
    )
    store.create_alert_rule(
        AlertRuleCreate(name="strict", condition="failure_rate > 0.9",
                        scope={"tool": "search"}, window_minutes=60, channel="log")
    )
    assert evaluate_rules(store) == []


def test_cooldown_prevents_refiring():
    store = DuckDBStore(":memory:")
    store.write_events(_failing_tool_run("r1"))
    store.create_alert_rule(
        AlertRuleCreate(name="once", condition="failure_rate > 0.1",
                        scope={"tool": "search"}, window_minutes=60, channel="log")
    )
    assert len(evaluate_rules(store)) == 1
    # Second evaluation within the window must not fire again.
    assert evaluate_rules(store) == []


def test_disabled_rule_never_fires():
    store = DuckDBStore(":memory:")
    store.write_events(_failing_tool_run("r1"))
    store.create_alert_rule(
        AlertRuleCreate(name="off", condition="failure_rate > 0.1",
                        scope={"tool": "search"}, window_minutes=60, channel="log", enabled=False)
    )
    assert evaluate_rules(store) == []


def test_webhook_dispatch(monkeypatch):
    store = DuckDBStore(":memory:")
    store.write_events(_failing_tool_run("r1"))
    posted = {}

    def fake_post(url, json, timeout):  # noqa: ANN001
        posted["url"] = url
        posted["payload"] = json

    monkeypatch.setattr("canary_server.alerting.httpx.post", fake_post)
    store.create_alert_rule(
        AlertRuleCreate(name="hook", condition="failure_rate > 0.1", scope={"tool": "search"},
                        window_minutes=60, channel="webhook", webhook_url="https://hook.test/x")
    )
    evaluate_rules(store)
    assert posted["url"] == "https://hook.test/x"
    assert "hook" in posted["payload"]["rule"]
