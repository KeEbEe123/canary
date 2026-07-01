"""``/v1/runs`` — list runs and fetch a single run's full trace."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import RunDetail, RunSummary
from ..store.base import EventStore
from . import get_store

router = APIRouter(prefix="/v1", tags=["runs"])


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    store: EventStore = Depends(get_store),
    agent: str | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(ok|error)$"),
    service: str | None = Query(default=None),
    start: float | None = Query(default=None, description="epoch seconds, inclusive lower bound"),
    end: float | None = Query(default=None, description="epoch seconds, inclusive upper bound"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[RunSummary]:
    return store.list_runs(
        agent=agent, status=status, service=service,
        start=start, end=end, limit=limit, offset=offset,
    )


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, store: EventStore = Depends(get_store)) -> RunDetail:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id!r} not found")
    return run
