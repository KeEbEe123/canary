# canary-sdk

**Sentry for AI agents.** Error tracking, not analytics.

```bash
pip install canary-sdk
```

```python
import canary
canary.init()  # local mode: DuckDB + dashboard on http://localhost:8732

@canary.trace("my_agent")
def run_agent(task: str):
    with canary.span("search", kind="tool", tool="web_search") as s:
        s.set_output(web_search(task))
    ...
```

Captures runs, LLM calls (model / tokens / latency / cost), tool invocations,
and errors (type, message, traceback, failing step) — and groups failures
Sentry-style so a spike on one tool is one line, not a thousand.

See the [project README](../README.md) for the full picture.

MIT licensed.
