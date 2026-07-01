"""Run the Canary server: ``python -m canary_server``.

Boots uvicorn against the env-configured store on port 8732 (override with
``CANARY_PORT``). This is the standalone entry point; local mode inside the SDK
boots the same app in-process instead.
"""

from __future__ import annotations

import os

import uvicorn

from .main import create_app


def main() -> None:
    port = int(os.environ.get("CANARY_PORT", "8732"))
    host = os.environ.get("CANARY_HOST", "127.0.0.1")
    app = create_app()
    print(f"🐤 Canary server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
