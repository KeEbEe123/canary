"""``POST /v1/events`` — batched span ingest from the SDK.

Validates the API key when the server runs with auth enabled (production),
persists the batch, then synchronously evaluates alert rules so a spike triggers
a firing on the very ingest that caused it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..alerting import evaluate_rules
from ..models import EventBatch, IngestResult
from ..store.base import EventStore
from . import get_store

router = APIRouter(prefix="/v1", tags=["events"])


def _check_auth(request: Request, key: str | None) -> None:
    """Enforce X-Canary-Key when the server was started with auth on."""
    config = request.app.state.config
    if config.require_auth and key != config.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing X-Canary-Key")


@router.post("/events", response_model=IngestResult)
def ingest_events(
    batch: EventBatch,
    request: Request,
    store: EventStore = Depends(get_store),
    x_canary_key: str | None = Header(default=None),
) -> IngestResult:
    _check_auth(request, x_canary_key)
    accepted = store.write_events([e.model_dump() for e in batch.events])
    fired = evaluate_rules(store)
    return IngestResult(accepted=accepted, alerts_fired=len(fired))
