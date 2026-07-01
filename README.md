<div align="center">

# 🐤 Canary

### Sentry for AI agents. Error tracking, not analytics.

**AI agents fail silently. Canary makes agent failures visible, fast.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
[![Zero config](https://img.shields.io/badge/local%20mode-zero%20config-success.svg)](#quickstart)

</div>

---

Your agent called the wrong tool. The LLM timed out. A `KeyError` got swallowed
three frames deep. The retry loop never terminated. You find out when a user
complains — or you don't find out at all.

**Canary auto-instruments your agent runs, captures the full trace when they
fail, groups failures Sentry-style, and alerts you when a tool or agent starts
breaking.** No dashboards for vanity metrics. No prompt management. No dataset
labeling. Just: *your agent broke, here's why, here's the pattern.*

## Quickstart

```bash
pip install canary-sdk
python -c "import canary; canary.init()"
```

That's it. Local mode spins up a DuckDB store and a dashboard at
**http://localhost:8732** — no Docker, no Postgres, no config.

## 3-step integration

Drop Canary into an existing agent in three lines:

```python
import canary
canary.init()                       # 1. start (local: DuckDB + dashboard on :8732)

@canary.trace("research_agent")     # 2. trace the run — errors captured automatically
def run_agent(task: str):
    with canary.span("search", kind="tool", tool="web_search") as s:  # 3. span your tools
        s.set_output(web_search(task))
    return summarize(task)

canary.instrument("openai")         # (optional) auto-capture model / tokens / cost / latency
```

When `run_agent` raises — or any tool span fails — Canary records the exception
type, message, traceback, and the exact step it failed at, then groups it with
every other occurrence of the same failure.

## What it captures

| Category         | Detail                                                                 |
|------------------|------------------------------------------------------------------------|
| **Run**          | agent name, task, start/end, status (success / error)                  |
| **LLM calls**    | model, prompt/completion tokens, latency, estimated cost               |
| **Tool calls**   | tool name, args, result, duration, success/fail                        |
| **Errors**       | exception type, message, full traceback, **which step it failed at**   |
| **Reasoning**    | optional thought → action → observation trace                          |

## Architecture

```
   ┌──────────────┐   in-process (local mode)   ┌───────────────┐      ┌────────────────┐
   │  canary-sdk  │ ──────────────────────────► │  EventStore   │ ───► │  DuckDB (local)│
   │  @trace      │                             │  (protocol)   │      │  ClickHouse*   │
   │  span()      │   batched HTTP (production)  │               │      └────────────────┘
   │  instrument()│ ──────────────────────────► │               │
   └──────────────┘                             └───────┬───────┘
         │  local mode boots the server in-process              │
         ▼                                                       ▼
   opens browser → :8732  ◄──────────────  FastAPI  /v1/*  +  React dashboard (static)

   * ClickHouse is the production backend (stubbed in v0.1, DuckDB is the default).
```

- **SDK** (`canary-sdk`) — decorator + context-manager tracing, async-safe,
  batched HTTP transport with retry, OpenAI/LangChain auto-instrumentation.
  Zero deps beyond `httpx`, `pydantic`, `duckdb` (`opentelemetry-api` optional).
- **Backend** (`canary-server`) — FastAPI collector, DuckDB store behind an
  `EventStore` protocol, Sentry-style error grouping, alert-rule engine.
- **Dashboard** — React + Tailwind + TanStack Query, dark mode, served as static
  assets by the backend.

## Dashboard

<!-- Screenshots — added after first run. -->

| Error Feed | Run Detail | Stats | Alerts |
|:---:|:---:|:---:|:---:|
| _grouped failures_ | _trace timeline_ | _7-day trend_ | _spike rules_ |
| ![Error Feed](docs/screenshot-errors.png) | ![Run Detail](docs/screenshot-run.png) | ![Stats](docs/screenshot-stats.png) | ![Alerts](docs/screenshot-alerts.png) |

- **Error Feed** — grouped error list (same exception + tool + agent = one
  group, even when the message varies). Click through to a sample trace.
- **Run Detail** — a flame-graph-style timeline of every span in a run: LLM
  calls, tool calls, errors, timing, and the captured traceback.
- **Stats** — total runs, success rate, error-rate trend, top failing tools/agents.
- **Alert Rules** — fire a webhook when e.g. `failure_rate > 0.3` on a tool.

## Alerting

Rules are simple and evaluated on every ingest:

```json
{
  "name": "search_tool_failing",
  "condition": "failure_rate > 0.3",
  "scope": { "tool": "search" },
  "window_minutes": 60,
  "channel": "webhook",
  "webhook_url": "https://hooks.example.com/..."
}
```

Conditions are parsed with a tiny grammar (never `eval`), so a rule string can't
execute code.

## How error grouping works

Two failures land in the same group when they share **exception type + tool +
agent + a normalised message**. The message is normalised to strip the parts
that vary run-to-run — numbers, hex ids, UUIDs, quoted literals, file paths — so
`Timeout after 3021ms` and `Timeout after 12ms` fingerprint together, while a
genuinely different error stays separate. (See `fingerprint.py`.)

## Production mode

```python
canary.init(api_key="...", endpoint="https://api.canary.dev")
```

Ships batched traces over HTTP (retry + backoff) to a remote collector, which
authenticates with the `X-Canary-Key` header. Point the backend at ClickHouse
with `CANARY_STORE=clickhouse` (see `docker-compose.yml`).

## Canary vs. the observability platforms

|                        | **Canary** | Laminar | Langfuse | Helicone |
|------------------------|:----------:|:-------:|:--------:|:--------:|
| Open source            | ✅         | ✅      | ✅       | ✅       |
| Zero-config local mode | ✅ DuckDB  | ❌      | ❌       | ❌       |
| **Agent-first**        | ✅         | ⚠️      | ⚠️      | ❌       |
| **Error-focused**      | ✅         | ❌      | ❌       | ❌       |
| Full LLM analytics     | ❌ (by design) | ✅  | ✅       | ✅       |
| Prompt management      | ❌ (by design) | ✅  | ✅       | ⚠️      |

Canary is not a full observability platform — it's an **error tracker**. Like
Sentry did for app errors, Canary does one thing for agents and does it well.
(And like PostHog started with analytics and expanded — Canary starts with error
tracking and can expand later.)

## Development

```bash
make install     # SDK + backend (editable) + dashboard deps
make test        # pytest across SDK and backend
make dashboard   # build the SPA into the backend's static dir
make dev         # run the server on :8732
make seed        # populate demo data so the dashboard looks alive
```

Repo layout: `sdk/` (the SDK), `backend/` (collector + dashboard host),
`dashboard/` (React SPA). See each package's README for details.

## License

MIT © 2026 Canary. See [LICENSE](./LICENSE).
