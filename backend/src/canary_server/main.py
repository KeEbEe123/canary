"""FastAPI application factory.

Wires the ``/v1`` routers to a shared :class:`EventStore` and serves the
compiled dashboard as a single-page app: static assets from ``static/`` and a
catch-all that returns ``index.html`` so client-side routing works on refresh.
When the dashboard hasn't been built yet, the catch-all serves a friendly
placeholder instead of a 404.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import ServerConfig
from .routes import alerts, errors, events, runs, stats

_PLACEHOLDER = """<!doctype html><html><head><meta charset="utf-8">
<title>Canary</title><style>
body{background:#0a0a0b;color:#e5e5e7;font-family:ui-sans-serif,system-ui,sans-serif;
display:grid;place-items:center;height:100vh;margin:0}
.c{text-align:center;max-width:34rem;padding:2rem}
code{background:#18181b;padding:.2rem .5rem;border-radius:.375rem;color:#fbbf24}
h1{font-size:2rem;margin:.25rem 0}.d{color:#a1a1aa}
</style></head><body><div class="c">
<div style="font-size:3rem">🐤</div>
<h1>Canary is running</h1>
<p class="d">The API is live at <code>/v1</code>. The dashboard bundle isn't built yet.</p>
<p class="d">Build it with <code>make dashboard</code> (or <code>cd dashboard && npm run build</code>),
then reload.</p></div></body></html>"""


def create_app(store: Optional[Any] = None, config: Optional[ServerConfig] = None) -> FastAPI:
    """Build the app. Pass ``store`` to share an in-process store (local mode)."""
    config = config or ServerConfig.from_env()
    if store is None:
        from .store import build_store

        store = build_store(config)

    app = FastAPI(
        title="Canary",
        description="Sentry for AI agents. Error tracking, not analytics.",
        version="0.1.0",
    )
    app.state.store = store
    app.state.config = config

    # CORS is convenient for the Vite dev server hitting the API on :8732.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (events, runs, errors, stats, alerts):
        app.include_router(module.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    _mount_dashboard(app, config)
    return app


def _mount_dashboard(app: FastAPI, config: ServerConfig) -> None:
    """Serve built SPA assets, falling back to a placeholder before first build."""
    static_dir = Path(config.static_dir)
    assets_dir = static_dir / "assets"
    index = static_dir / "index.html"

    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> Any:
        # Never shadow the API namespace.
        if full_path.startswith(("v1/", "health")):
            return HTMLResponse("Not Found", status_code=404)
        # Serve real files (favicon, etc.) when they exist.
        candidate = static_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        if index.is_file():
            return FileResponse(str(index))
        return HTMLResponse(_PLACEHOLDER)


# A module-level app so `uvicorn canary_server.main:app` works out of the box.
app = create_app() if os.environ.get("CANARY_EAGER_APP") else None
