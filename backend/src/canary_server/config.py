"""Server configuration, resolved from ``CANARY_*`` environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel

DEFAULT_DB_PATH = str(Path.home() / ".canary" / "canary.duckdb")
STATIC_DIR = str(Path(__file__).parent / "static")


class ServerConfig(BaseModel):
    """Runtime configuration for the FastAPI app."""

    # Storage backend: "duckdb" (default, zero-config) or "clickhouse".
    store: str = "duckdb"
    db_path: str = DEFAULT_DB_PATH

    # When true, ``POST /v1/events`` requires a matching X-Canary-Key header.
    # Local mode leaves this false so the SDK can write without auth.
    require_auth: bool = False
    api_key: str | None = None

    static_dir: str = STATIC_DIR

    @classmethod
    def from_env(cls) -> "ServerConfig":
        api_key = os.environ.get("CANARY_API_KEY")
        return cls(
            store=os.environ.get("CANARY_STORE", "duckdb"),
            db_path=os.environ.get("CANARY_DB_PATH", DEFAULT_DB_PATH),
            # Auth is on whenever an API key is configured.
            require_auth=bool(api_key),
            api_key=api_key,
            static_dir=os.environ.get("CANARY_STATIC_DIR", STATIC_DIR),
        )
