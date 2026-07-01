"""``GET /v1/stats`` — aggregate overview for the stats page."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models import Stats
from ..store.base import EventStore
from . import get_store

router = APIRouter(prefix="/v1", tags=["stats"])


@router.get("/stats", response_model=Stats)
def get_stats(
    store: EventStore = Depends(get_store),
    days: int = Query(default=7, ge=1, le=90, description="trailing window for the trend chart"),
) -> Stats:
    return store.stats(days=days)
