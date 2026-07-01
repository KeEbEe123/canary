"""Alert rule evaluation.

Rules are deliberately simple: a metric, a comparison, a threshold, over a time
window, optionally scoped to one tool or agent. Example::

    {"name": "search failing", "condition": "failure_rate > 0.3",
     "scope": {"tool": "search"}, "window_minutes": 60, "channel": "webhook",
     "webhook_url": "https://hooks.example.com/..."}

Conditions are parsed with a tiny regex grammar — **never** ``eval`` — so a
malicious rule string can't execute code. After each ingest we re-evaluate every
enabled rule and fire the ones that cross their threshold (with a per-rule
cooldown of one window so a sustained spike doesn't spam the channel).
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING

import httpx

from .models import AlertFiring, AlertRule

if TYPE_CHECKING:  # avoid import cycle at runtime
    from .store.base import EventStore

logger = logging.getLogger("canary.alerting")

# Left-hand metrics a condition may reference, mapped to scope_metrics() keys.
_METRICS = {"failure_rate", "error_count", "total"}
_METRIC_ALIASES = {"error_count": "errors", "total": "total", "failure_rate": "failure_rate"}
_CONDITION_RE = re.compile(r"^\s*(\w+)\s*(>=|<=|>|<|==)\s*([0-9]*\.?[0-9]+)\s*$")


class ConditionError(ValueError):
    """Raised when an alert condition string can't be parsed."""


def parse_condition(condition: str) -> tuple[str, str, float]:
    """Parse ``"failure_rate > 0.3"`` into ``("failure_rate", ">", 0.3)``."""
    match = _CONDITION_RE.match(condition or "")
    if not match:
        raise ConditionError(f"invalid condition: {condition!r} (expected e.g. 'failure_rate > 0.3')")
    metric, op, threshold = match.group(1), match.group(2), float(match.group(3))
    if metric not in _METRICS:
        raise ConditionError(f"unknown metric {metric!r}; choose from {sorted(_METRICS)}")
    return metric, op, threshold


def _compare(value: float, op: str, threshold: float) -> bool:
    return {
        ">": value > threshold,
        ">=": value >= threshold,
        "<": value < threshold,
        "<=": value <= threshold,
        "==": value == threshold,
    }[op]


def _recently_fired(store: "EventStore", rule: AlertRule) -> bool:
    """True if this rule fired within its own window (cooldown)."""
    cutoff = time.time() - rule.window_minutes * 60
    return any(
        f.rule_id == rule.id and f.fired_at >= cutoff
        for f in store.list_alert_firings(limit=100)
    )


def evaluate_rules(store: "EventStore") -> list[AlertFiring]:
    """Evaluate all enabled rules; fire and return any that crossed threshold."""
    fired: list[AlertFiring] = []
    for rule in store.list_alert_rules():
        if not rule.enabled:
            continue
        try:
            metric, op, threshold = parse_condition(rule.condition)
        except ConditionError as exc:
            logger.warning("skipping rule %s: %s", rule.name, exc)
            continue

        metrics = store.scope_metrics(
            tool=rule.scope.tool, agent=rule.scope.agent, window_minutes=rule.window_minutes
        )
        value = metrics[_METRIC_ALIASES[metric]]
        if not _compare(value, op, threshold):
            continue
        if _recently_fired(store, rule):
            continue

        message = (
            f"Alert '{rule.name}': {metric} = {value} {op} {threshold} "
            f"over {rule.window_minutes}m"
            + (f" [tool={rule.scope.tool}]" if rule.scope.tool else "")
            + (f" [agent={rule.scope.agent}]" if rule.scope.agent else "")
        )
        firing = store.record_firing(rule, value, message)
        _dispatch(rule, firing)
        fired.append(firing)
    return fired


def _dispatch(rule: AlertRule, firing: AlertFiring) -> None:
    """Send the firing to its channel. Best-effort — never blocks ingest."""
    if rule.channel == "webhook" and rule.webhook_url:
        try:
            httpx.post(
                rule.webhook_url,
                json={
                    "rule": rule.name,
                    "message": firing.message,
                    "value": firing.value,
                    "fired_at": firing.fired_at,
                },
                timeout=5.0,
            )
        except httpx.HTTPError as exc:  # noqa: BLE001 - dead webhook shouldn't 500 ingest
            logger.warning("webhook for rule %s failed: %s", rule.name, exc)
    else:
        logger.warning("ALERT %s", firing.message)
