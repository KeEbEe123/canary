"""``/v1/alerts`` — CRUD for alert rules plus recent firings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..alerting import ConditionError, parse_condition
from ..models import AlertRule, AlertRuleCreate, AlertsResponse
from ..store.base import EventStore
from . import get_store

router = APIRouter(prefix="/v1", tags=["alerts"])


@router.get("/alerts", response_model=AlertsResponse)
def list_alerts(store: EventStore = Depends(get_store)) -> AlertsResponse:
    return AlertsResponse(
        rules=store.list_alert_rules(),
        recent_firings=store.list_alert_firings(limit=50),
    )


@router.post("/alerts", response_model=AlertRule, status_code=201)
def create_alert(rule: AlertRuleCreate, store: EventStore = Depends(get_store)) -> AlertRule:
    # Validate the condition up front so a bad rule fails loudly at create time,
    # not silently at evaluation time.
    try:
        parse_condition(rule.condition)
    except ConditionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if rule.channel == "webhook" and not rule.webhook_url:
        raise HTTPException(status_code=422, detail="webhook channel requires a webhook_url")
    return store.create_alert_rule(rule)
