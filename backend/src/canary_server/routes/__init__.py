"""FastAPI routers for the Canary API, all mounted under ``/v1``.

Every route resolves its :class:`EventStore` through the :func:`get_store`
dependency, which reads the single store instance off ``app.state`` — so the
same store the SDK writes to (local mode) is the one the API reads from.
"""

from __future__ import annotations

from fastapi import Request

from ..store.base import EventStore


def get_store(request: Request) -> EventStore:
    """Dependency: the process's shared event store."""
    return request.app.state.store
