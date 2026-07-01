"""Tests for canary.span(): nesting, parent links, output, error propagation."""

from __future__ import annotations

import pytest

import canary


def test_span_nesting_and_parent_links(client, transport):
    @canary.trace("agent")
    def run() -> None:
        with canary.span("outer", kind="tool", tool="a"):
            with canary.span("inner", kind="tool", tool="b"):
                pass

    run()

    events = {e["name"]: e for e in transport.events}
    run_ev, outer, inner = events["agent"], events["outer"], events["inner"]

    # All share the run id; parent chain is inner -> outer -> run.
    assert outer["run_id"] == inner["run_id"] == run_ev["run_id"]
    assert outer["parent_id"] == run_ev["span_id"]
    assert inner["parent_id"] == outer["span_id"]


def test_span_set_output_and_attributes(client, transport):
    @canary.trace("agent")
    def run() -> None:
        with canary.span("search", kind="tool", tool="web") as s:
            s.set_output(["r1", "r2"])
            s.set_attribute("hits", 2)

    run()

    span = next(e for e in transport.events if e["name"] == "search")
    assert span["output"] == ["r1", "r2"]
    assert span["attributes"]["hits"] == 2
    assert span["kind"] == "tool"


def test_span_error_marks_span_and_run(client, transport):
    @canary.trace("agent")
    def run() -> None:
        with canary.span("db", kind="tool", tool="sql"):
            raise KeyError("missing")

    with pytest.raises(KeyError):
        run()

    span = next(e for e in transport.events if e["name"] == "db")
    run_ev = next(e for e in transport.events if e["kind"] == "run")
    assert span["status"] == "error"
    assert span["error"]["type"] == "KeyError"
    # The failure propagates to the run status...
    assert run_ev["status"] == "error"
    # ...but the run does NOT double-record the same error as its own group.
    assert run_ev["error"] is None


def test_context_restored_after_span(client, transport):
    """Sibling spans should both parent to the run, not to each other."""

    @canary.trace("agent")
    def run() -> None:
        with canary.span("first", kind="tool", tool="a"):
            pass
        with canary.span("second", kind="tool", tool="b"):
            pass

    run()

    run_ev = next(e for e in transport.events if e["kind"] == "run")
    first = next(e for e in transport.events if e["name"] == "first")
    second = next(e for e in transport.events if e["name"] == "second")
    assert first["parent_id"] == run_ev["span_id"]
    assert second["parent_id"] == run_ev["span_id"]


def test_thought_action_observation_recorded(client, transport):
    @canary.trace("agent")
    def run() -> None:
        canary.record("I should search", "call search", "found 3 docs")

    run()
    run_ev = next(e for e in transport.events if e["kind"] == "run")
    thoughts = run_ev["attributes"]["thoughts"]
    assert thoughts == [{"thought": "I should search", "action": "call search", "observation": "found 3 docs"}]
