# canary-server

The Canary collector + dashboard host: a FastAPI app that ingests span events
from the SDK, stores them (DuckDB locally, ClickHouse in production), groups
errors, evaluates alert rules, and serves the dashboard.

```bash
pip install canary-server
python -m canary_server          # http://localhost:8732
python -m canary_server.seed     # populate demo data
```

## API (`/v1`)

| Method | Path              | Purpose                                  |
|--------|-------------------|------------------------------------------|
| POST   | `/v1/events`      | Ingest batched spans from the SDK        |
| GET    | `/v1/runs`        | List runs (filter by agent/status/time)  |
| GET    | `/v1/runs/{id}`   | Full trace for one run                   |
| GET    | `/v1/errors`      | Failures grouped by fingerprint          |
| GET    | `/v1/stats`       | Aggregate overview + 7-day trend         |
| GET    | `/v1/alerts`      | Alert rules + recent firings             |
| POST   | `/v1/alerts`      | Create an alert rule                      |

Storage is abstracted behind the `EventStore` protocol (`store/base.py`). Set
`CANARY_STORE=clickhouse` to select the production backend (stubbed in v0.1).

MIT licensed.
