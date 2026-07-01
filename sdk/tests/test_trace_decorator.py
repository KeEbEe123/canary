"""Tests for the @canary.trace decorator: success, failure, async, failing step."""

from __future__ import annotations

import asyncio

import pytest

import canary


def test_trace_captures_successful_run(client, transport):
    @canary.trace("greeter")
    def greet(name: str) -> str:
        return f"hi {name}"

    assert greet("ada") == "hi ada"

    runs = transport.by_kind("run")
    assert len(runs) == 1
    run = runs[0]
    assert run["name"] == "greeter"
    assert run["status"] == "ok"
    assert run["input"] == "ada"          # first arg captured as the task
    assert run["output"] == "hi ada"
    assert run["duration_ms"] is not None


def test_trace_captures_exception_and_reraises(client, transport):
    @canary.trace("boom")
    def explode() -> None:
        raise ValueError("kaboom 42")

    with pytest.raises(ValueError, match="kaboom 42"):
        explode()

    run = transport.by_kind("run")[0]
    assert run["status"] == "error"
    err = run["error"]
    assert err["type"] == "ValueError"
    assert err["message"] == "kaboom 42"
    assert "Traceback" in err["traceback"]
    # The failing step points at the frame where it blew up.
    assert "explode" in err["failed_at"]
    assert len(err["fingerprint"]) == 16


def test_trace_bare_decorator_uses_function_name(client, transport):
    @canary.trace
    def my_agent() -> int:
        return 1

    assert my_agent() == 1
    assert transport.by_kind("run")[0]["name"] == "my_agent"


def test_trace_async_function(client, transport):
    @canary.trace("async_agent")
    async def work(task: str) -> str:
        await asyncio.sleep(0)
        return task.upper()

    assert asyncio.run(work("go")) == "GO"
    run = transport.by_kind("run")[0]
    assert run["status"] == "ok"
    assert run["output"] == "GO"


def test_trace_async_error(client, transport):
    @canary.trace("async_boom")
    async def fail() -> None:
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        asyncio.run(fail())

    assert transport.errors()[0]["error"]["type"] == "RuntimeError"
