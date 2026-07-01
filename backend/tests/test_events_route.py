"""Tests for the ingest route, including production-mode API-key auth."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from canary_server.config import ServerConfig
from canary_server.main import create_app
from canary_server.store.duckdb_store import DuckDBStore


def _event(run_id: str = "r1", status: str = "ok") -> dict:
    return {
        "span_id": f"{run_id}-root", "run_id": run_id, "name": "agent", "kind": "run",
        "status": status, "start_time": time.time(), "attributes": {"agent": "agent", "service": "t"},
    }


@pytest.fixture
def client_local() -> TestClient:
    app = create_app(store=DuckDBStore(":memory:"), config=ServerConfig(require_auth=False))
    return TestClient(app)


def test_ingest_accepts_batch(client_local: TestClient):
    resp = client_local.post("/v1/events", json={"events": [_event()], "service": "t"})
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1
    # And the run is now queryable.
    assert len(client_local.get("/v1/runs").json()) == 1


def test_ingest_no_auth_required_in_local_mode(client_local: TestClient):
    resp = client_local.post("/v1/events", json={"events": [_event()]})
    assert resp.status_code == 200


def test_ingest_rejects_bad_key_in_production():
    app = create_app(
        store=DuckDBStore(":memory:"),
        config=ServerConfig(require_auth=True, api_key="secret"),
    )
    client = TestClient(app)

    # Missing key -> 401.
    assert client.post("/v1/events", json={"events": [_event()]}).status_code == 401
    # Wrong key -> 401.
    bad = client.post("/v1/events", json={"events": [_event()]}, headers={"X-Canary-Key": "nope"})
    assert bad.status_code == 401
    # Correct key -> accepted.
    ok = client.post("/v1/events", json={"events": [_event()]}, headers={"X-Canary-Key": "secret"})
    assert ok.status_code == 200


def test_health_endpoint(client_local: TestClient):
    assert client_local.get("/health").json()["status"] == "ok"
