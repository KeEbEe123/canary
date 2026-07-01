"""Storage backends for Canary.

``EventStore`` is the protocol every backend implements. ``DuckDBStore`` is the
zero-config local default; ``ClickHouseStore`` is the production stub. Use
:func:`build_store` to pick one from config.
"""

from __future__ import annotations

from ..config import ServerConfig
from .base import EventStore


def build_store(config: ServerConfig) -> EventStore:
    """Instantiate the configured store backend."""
    if config.store == "clickhouse":
        from .clickhouse_store import ClickHouseStore

        return ClickHouseStore(config.db_path)
    from .duckdb_store import DuckDBStore

    return DuckDBStore(config.db_path)


__all__ = ["EventStore", "build_store"]
