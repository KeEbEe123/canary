"""Canary server: the collector + dashboard host.

Ingests span events from the SDK, persists them behind an :class:`EventStore`
(DuckDB locally, ClickHouse in production), groups errors, evaluates alert
rules, and serves both the JSON API under ``/v1`` and the compiled dashboard.
"""

__version__ = "0.1.0"
