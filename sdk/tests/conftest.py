"""Shared SDK test fixtures.

Provides a ``client`` fixture that wires a real :class:`CanaryClient` to a
``CapturingTransport`` (spans land in a list instead of DuckDB/HTTP), and resets
the process-global client between tests so state never leaks.
"""

from __future__ import annotations

from typing import Any

import pytest

import canary.client as cc
from canary.client import CanaryClient
from canary.config import CanaryConfig, Mode


class CapturingTransport:
    """Test double: records every emitted span event."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    def flush(self) -> None:  # noqa: D102
        pass

    def shutdown(self) -> None:  # noqa: D102
        pass

    # Convenience filters used across tests.
    def by_kind(self, kind: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["kind"] == kind]

    def errors(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e["status"] == "error"]


@pytest.fixture
def transport() -> CapturingTransport:
    return CapturingTransport()


@pytest.fixture
def client(transport: CapturingTransport):
    """Install a capturing client as the process global; tear it down after."""
    config = CanaryConfig(mode=Mode.LOCAL, launch_dashboard=False, service="test", sample_rate=1.0)
    instance = CanaryClient(config, transport)
    cc._client = instance
    yield instance
    cc._client = None
