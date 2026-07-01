"""Tests for transports: direct in-process writes and batched HTTP with retry."""

from __future__ import annotations

import httpx
import pytest

from canary.config import CanaryConfig, Mode
from canary.transport import DirectTransport, HTTPTransport, build_transport


class FakeStore:
    def __init__(self) -> None:
        self.written: list[dict] = []

    def write_events(self, events):  # noqa: ANN001
        self.written.extend(events)


def test_direct_transport_writes_to_store():
    store = FakeStore()
    t = DirectTransport(store)
    t.emit({"span_id": "1", "run_id": "r"})
    t.flush()
    assert store.written == [{"span_id": "1", "run_id": "r"}]


def test_build_transport_local_requires_store():
    cfg = CanaryConfig(mode=Mode.LOCAL)
    with pytest.raises(ValueError):
        build_transport(cfg, store=None)
    assert isinstance(build_transport(cfg, store=FakeStore()), DirectTransport)


def _prod_config(**kw) -> CanaryConfig:
    return CanaryConfig(
        mode=Mode.PRODUCTION, api_key="k", endpoint="https://collector.test",
        flush_interval=3600, **kw,  # long interval so the bg thread stays out of the way
    )


def test_http_transport_batches_on_threshold():
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"accepted": 1})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    t = HTTPTransport(_prod_config(batch_size=3), client=client)
    try:
        t.emit({"span_id": "1"})
        t.emit({"span_id": "2"})
        assert len(calls) == 0            # below threshold, still buffered
        t.emit({"span_id": "3"})          # hits batch_size → flush
        assert len(calls) == 1
    finally:
        t.shutdown()


def test_http_transport_sends_api_key_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("X-Canary-Key")
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    t = HTTPTransport(_prod_config(), client=client)
    try:
        t.emit({"span_id": "1"})
        t.flush()
        assert seen["key"] == "k"
    finally:
        t.shutdown()


def test_http_transport_retries_then_succeeds(monkeypatch):
    # Avoid real backoff sleeps.
    monkeypatch.setattr("canary.transport.time.sleep", lambda *_: None)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    t = HTTPTransport(_prod_config(max_retries=5), client=client)
    try:
        t.emit({"span_id": "1"})
        t.flush()
        assert attempts["n"] == 3          # 2 failures + 1 success
    finally:
        t.shutdown()


def test_http_transport_drops_after_max_retries(monkeypatch):
    monkeypatch.setattr("canary.transport.time.sleep", lambda *_: None)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    t = HTTPTransport(_prod_config(max_retries=2), client=client)
    try:
        t.emit({"span_id": "1"})
        t.flush()  # must not raise even though every attempt failed
        assert attempts["n"] == 3          # initial + 2 retries, then dropped
    finally:
        t.shutdown()


def test_http_transport_drops_fast_on_4xx(monkeypatch):
    monkeypatch.setattr("canary.transport.time.sleep", lambda *_: None)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    t = HTTPTransport(_prod_config(max_retries=5), client=client)
    try:
        t.emit({"span_id": "1"})
        t.flush()
        assert attempts["n"] == 1          # 4xx won't be retried
    finally:
        t.shutdown()
