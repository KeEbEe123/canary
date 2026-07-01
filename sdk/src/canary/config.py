"""Canary SDK configuration.

Holds the runtime configuration for the SDK. Values can be passed directly to
``canary.init()`` or supplied through ``CANARY_*`` environment variables. When
no ``api_key`` is present the SDK runs in *local* mode: it boots an in-process
FastAPI dashboard and writes traces straight to a local DuckDB file. When an
``api_key`` is set it runs in *production* mode and ships batched events over
HTTP to a remote collector.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Mode(str, Enum):
    """Where captured traces are sent."""

    LOCAL = "local"
    PRODUCTION = "production"


# The port the local dashboard + collector listens on. Chosen to be memorable
# and unlikely to collide: 8732 == "TRACE" on a phone keypad-ish mnemonic.
DEFAULT_PORT = 8732
DEFAULT_ENDPOINT = "https://api.canary.dev"
DEFAULT_DB_PATH = str(Path.home() / ".canary" / "canary.duckdb")


class CanaryConfig(BaseModel):
    """Resolved SDK configuration.

    Precedence (highest first): explicit ``init()`` argument > ``CANARY_*``
    environment variable > built-in default.
    """

    mode: Mode = Mode.LOCAL
    api_key: str | None = None
    endpoint: str = DEFAULT_ENDPOINT
    port: int = DEFAULT_PORT
    db_path: str = DEFAULT_DB_PATH

    # Service identity, attached to every run so multiple apps can share a store.
    service: str = "default"

    # Transport batching knobs (production/HTTP mode only).
    batch_size: int = Field(default=100, ge=1)
    flush_interval: float = Field(default=2.0, gt=0)
    max_retries: int = Field(default=5, ge=0)

    # Fraction of runs to keep (1.0 == everything). Errors are always kept.
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    # Whether local mode should boot the dashboard server + open a browser.
    launch_dashboard: bool = True
    open_browser: bool = True

    @classmethod
    def resolve(cls, **overrides: object) -> "CanaryConfig":
        """Build config from ``init()`` overrides layered over the environment."""

        def env(name: str) -> str | None:
            return os.environ.get(f"CANARY_{name}")

        api_key = overrides.get("api_key") or env("API_KEY")
        # Presence of an API key implies production unless caller says otherwise.
        default_mode = Mode.PRODUCTION if api_key else Mode.LOCAL
        raw_mode = overrides.get("mode") or env("MODE") or default_mode

        values: dict[str, object] = {
            "mode": Mode(raw_mode) if not isinstance(raw_mode, Mode) else raw_mode,
            "api_key": api_key,
            "endpoint": overrides.get("endpoint") or env("ENDPOINT") or DEFAULT_ENDPOINT,
            "port": int(overrides.get("port") or env("PORT") or DEFAULT_PORT),
            "db_path": overrides.get("db_path") or env("DB_PATH") or DEFAULT_DB_PATH,
            "service": overrides.get("service") or env("SERVICE") or "default",
        }
        for key in ("batch_size", "flush_interval", "max_retries", "sample_rate"):
            if overrides.get(key) is not None:
                values[key] = overrides[key]
        for flag in ("launch_dashboard", "open_browser"):
            if overrides.get(flag) is not None:
                values[flag] = overrides[flag]
        return cls(**values)

    @property
    def is_local(self) -> bool:
        return self.mode == Mode.LOCAL
