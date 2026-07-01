"""``GET /v1/errors`` — failures grouped Sentry-style by fingerprint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models import ErrorGroup
from ..store.base import EventStore
from . import get_store

router = APIRouter(prefix="/v1", tags=["errors"])


@router.get("/errors", response_model=list[ErrorGroup])
def list_errors(
    store: EventStore = Depends(get_store),
    agent: str | None = Query(default=None),
    tool: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[ErrorGroup]:
    return store.list_error_groups(agent=agent, tool=tool, limit=limit)
