"""Boot the Canary dashboard + collector in-process for local mode.

``canary.init()`` (no api key) calls :func:`start_local_server`, which:

1. Opens a DuckDB-backed :class:`EventStore` from the ``canary-server`` package.
2. Starts the FastAPI app (which serves ``/v1/*`` and the built dashboard) on a
   daemon uvicorn thread bound to the configured port.
3. Optionally opens the dashboard in a browser.

The **same** store object is handed back to the SDK so its ``DirectTransport``
writes to exactly the connection the dashboard reads from — one writer, zero
lock contention, no HTTP round-trip for local capture.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .config import CanaryConfig

logger = logging.getLogger("canary")

# Module-level guard so repeated init() calls don't spawn multiple servers.
_lock = threading.Lock()
_store: Any = None
_server_thread: threading.Thread | None = None


def start_local_server(config: CanaryConfig) -> Any:
    """Start (once) the local server and return the shared EventStore."""
    global _store, _server_thread
    with _lock:
        if _store is not None:
            return _store

        try:
            from canary_server.store.duckdb_store import DuckDBStore
        except ImportError as exc:  # pragma: no cover - install hint
            raise ImportError(
                "Local mode needs the dashboard server. Install it with:\n"
                '    pip install "canary-sdk[server]"\n'
                "or run in production mode with canary.init(api_key=...)."
            ) from exc

        _store = DuckDBStore(config.db_path)

        if config.launch_dashboard:
            _server_thread = _spawn_server(config, _store)
            if config.open_browser:
                _open_browser(config.port)

        return _store


def _spawn_server(config: CanaryConfig, store: Any) -> threading.Thread:
    """Run uvicorn in a daemon thread against the shared store."""
    import uvicorn
    from canary_server.main import create_app

    app = create_app(store=store)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=config.port, log_level="warning")
    )

    def _serve() -> None:
        server.run()

    thread = threading.Thread(target=_serve, name="canary-dashboard", daemon=True)
    thread.start()

    # Give uvicorn a beat to bind so the first browser hit isn't a refused conn.
    for _ in range(50):
        if getattr(server, "started", False):
            break
        time.sleep(0.05)
    logger.info("Canary dashboard running at http://localhost:%s", config.port)
    print(f"🐤 Canary is live at http://localhost:{config.port}")
    return thread


def _open_browser(port: int) -> None:
    """Open the dashboard, swallowing failures on headless machines."""
    import webbrowser

    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:  # noqa: BLE001 - headless / no browser is fine
        pass
