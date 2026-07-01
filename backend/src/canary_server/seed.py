"""Seed the local store with realistic demo data.

``python -m canary_server.seed`` populates the configured DuckDB file with a
week of agent runs — a mix of successes and failures across a few agents and
tools, LLM calls with token/cost, and clustered errors — so the dashboard looks
alive on first launch. Idempotent-ish: it appends, so run once on a fresh DB.
"""

from __future__ import annotations

import random
import time
import uuid

from .config import ServerConfig
from .fingerprint import fingerprint
from .store import build_store

AGENTS = ["research_agent", "support_bot", "code_reviewer", "sql_analyst"]
TOOLS = ["web_search", "sql_query", "code_exec", "vector_lookup", "http_fetch"]
MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

# Realistic failure archetypes. The message templates vary per instance (ids,
# numbers, paths) but normalise to the same fingerprint — that's the point.
FAILURES = [
    ("web_search", "TimeoutError", "Request timed out after {n}ms to https://api.search/{id}"),
    ("sql_query", "ProgrammingError", "syntax error at or near \"{tok}\" (line {n})"),
    ("code_exec", "ValueError", "invalid literal for int() with base 10: '{tok}'"),
    ("vector_lookup", "ConnectionError", "failed to connect to index shard {n} at /var/idx/{id}"),
    ("http_fetch", "HTTPError", "503 Service Unavailable for /v2/resource/{id}"),
]


def _id() -> str:
    return uuid.uuid4().hex


def _new_event(**kw: object) -> dict:
    base = {
        "span_id": _id(), "parent_id": None, "kind": "span", "status": "ok",
        "end_time": None, "duration_ms": None, "attributes": {}, "input": None,
        "output": None, "error": None, "otel_trace_id": None, "otel_span_id": None,
    }
    base.update(kw)
    return base


def build_demo_events(*, num_runs: int = 120) -> list[dict]:
    """Generate a week of demo spans across agents/tools with clustered errors."""
    now = time.time()
    events: list[dict] = []
    for _ in range(num_runs):
        agent = random.choice(AGENTS)
        start = now - random.uniform(0, 7 * 86400)
        run_id = _id()
        run_span = _new_event(
            span_id=_id(), run_id=run_id, name=agent, kind="run", status="ok",
            start_time=start, attributes={"agent": agent, "service": "demo", "thoughts": []},
            input=f"handle task #{random.randint(1000, 9999)}",
        )
        cursor = start
        run_failed = False

        # 1-3 LLM calls.
        for _ in range(random.randint(1, 3)):
            model = random.choice(MODELS)
            pt, ct = random.randint(200, 2000), random.randint(50, 800)
            dur = random.uniform(200, 3000)
            cost = round(pt / 1000 * 0.0025 + ct / 1000 * 0.01, 6)
            events.append(_new_event(
                run_id=run_id, parent_id=run_span["span_id"], name=f"openai.{model}", kind="llm",
                start_time=cursor, end_time=cursor + dur / 1000, duration_ms=round(dur, 2),
                attributes={"agent": agent, "model": model, "prompt_tokens": pt,
                            "completion_tokens": ct, "total_tokens": pt + ct,
                            "cost_usd": cost, "latency_ms": round(dur, 2)},
            ))
            cursor += dur / 1000

        # 1-4 tool calls; ~22% of runs hit a failing tool.
        for _ in range(random.randint(1, 4)):
            dur = random.uniform(20, 1500)
            if random.random() < 0.22:
                tool, etype, template = random.choice(FAILURES)
                msg = template.format(n=random.randint(1, 9000), id=_id()[:8],
                                      tok=random.choice(["foo", "NULL", "x9", "SELECT"]))
                events.append(_new_event(
                    run_id=run_id, parent_id=run_span["span_id"], name=tool, kind="tool", status="error",
                    start_time=cursor, end_time=cursor + dur / 1000, duration_ms=round(dur, 2),
                    attributes={"agent": agent, "tool": tool},
                    error={"type": etype, "message": msg, "traceback": f"Traceback...\n{etype}: {msg}",
                           "failed_at": f"{tool} (tools.py:{random.randint(10, 200)})",
                           "fingerprint": fingerprint(etype, tool=tool, agent=agent, message=msg)},
                ))
                run_failed = True
            else:
                tool = random.choice(TOOLS)
                events.append(_new_event(
                    run_id=run_id, parent_id=run_span["span_id"], name=tool, kind="tool", status="ok",
                    start_time=cursor, end_time=cursor + dur / 1000, duration_ms=round(dur, 2),
                    attributes={"agent": agent, "tool": tool}, output="ok",
                ))
            cursor += dur / 1000

        run_span["end_time"] = cursor
        run_span["duration_ms"] = round((cursor - start) * 1000, 2)
        run_span["status"] = "error" if run_failed else "ok"
        events.append(run_span)
    return events


def main() -> None:
    config = ServerConfig.from_env()
    store = build_store(config)
    events = build_demo_events()
    written = store.write_events(events)
    print(f"🌱 Seeded {written} spans into {config.db_path}")


if __name__ == "__main__":
    main()
