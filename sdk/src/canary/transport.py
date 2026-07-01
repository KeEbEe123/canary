"""Transports move captured spans out of the SDK.

Two implementations back the two modes:

* :class:`DirectTransport` — *local* mode. Writes spans straight into an
  in-process :class:`EventStore` (the same object the bundled dashboard reads),
  so there is exactly one DuckDB writer and no HTTP hop.
* :class:`HTTPTransport` — *production* mode. Buffers spans and ships them in
  batches to a remote collector over HTTP, with a background flush thread and
  exponential-backoff retries.

Both satisfy the :class:`Transport` protocol so the client is agnostic.
"""

from __future__ import annotations

import atexit
import threading
import time
from typing import Any, Protocol, runtime_checkable

import httpx

from .config import CanaryConfig


@runtime_checkable
class Transport(Protocol):
    """Anything that can accept and eventually persist span events."""

    def emit(self, event: dict[str, Any]) -> None: ...
    def flush(self) -> None: ...
    def shutdown(self) -> None: ...


class NoopTransport:
    """Discards everything. Used when sampling drops a run or for tests."""

    def emit(self, event: dict[str, Any]) -> None:  # noqa: D102
        pass

    def flush(self) -> None:  # noqa: D102
        pass

    def shutdown(self) -> None:  # noqa: D102
        pass


class DirectTransport:
    """Local mode: write spans directly to an in-process store.

    ``store`` is any object exposing ``write_events(list[dict])`` — in practice
    the backend's DuckDB store, injected by ``local_server``. Writes are guarded
    by a lock because spans can finish on worker threads.
    """

    def __init__(self, store: Any) -> None:
        self._store = store
        self._lock = threading.Lock()

    def emit(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._store.write_events([event])

    def flush(self) -> None:
        # Writes are synchronous, so nothing is buffered.
        pass

    def shutdown(self) -> None:
        self.flush()


class HTTPTransport:
    """Production mode: batched, retrying HTTP delivery.

    Spans are appended to an in-memory buffer. A daemon thread flushes the
    buffer every ``flush_interval`` seconds, or immediately once it reaches
    ``batch_size``. Failed flushes retry with exponential backoff; after
    ``max_retries`` the batch is dropped with a warning so the app is never
    blocked by a dead collector.
    """

    def __init__(self, config: CanaryConfig, *, client: httpx.Client | None = None) -> None:
        self._config = config
        self._endpoint = config.endpoint.rstrip("/") + "/v1/events"
        self._headers = {"X-Canary-Key": config.api_key or "", "Content-Type": "application/json"}
        self._client = client or httpx.Client(timeout=10.0)
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._flusher = threading.Thread(target=self._run, name="canary-flush", daemon=True)
        self._flusher.start()
        atexit.register(self.shutdown)

    # --- public API ---------------------------------------------------------

    def emit(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._buffer.append(event)
            over_threshold = len(self._buffer) >= self._config.batch_size
        if over_threshold:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            batch, self._buffer = self._buffer, []
        if batch:
            self._send_with_retry(batch)

    def shutdown(self) -> None:
        self._stop.set()
        self.flush()
        if self._flusher.is_alive():
            self._flusher.join(timeout=self._config.flush_interval + 1)
        self._client.close()

    # --- internals ----------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.wait(self._config.flush_interval):
            self.flush()

    def _send_with_retry(self, batch: list[dict[str, Any]]) -> None:
        payload = {"events": batch, "service": self._config.service}
        delay = 0.5
        for attempt in range(self._config.max_retries + 1):
            try:
                resp = self._client.post(self._endpoint, json=payload, headers=self._headers)
                if resp.status_code < 300:
                    return
                # 4xx (except 429) won't be fixed by retrying — drop fast.
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    self._warn(f"collector rejected batch ({resp.status_code}); dropping {len(batch)} spans")
                    return
            except httpx.HTTPError as exc:
                if attempt == self._config.max_retries:
                    self._warn(f"giving up after {attempt + 1} attempts ({exc}); dropping {len(batch)} spans")
                    return
            if attempt < self._config.max_retries:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)  # capped exponential backoff

    @staticmethod
    def _warn(message: str) -> None:
        import logging

        logging.getLogger("canary").warning("canary transport: %s", message)


def build_transport(config: CanaryConfig, *, store: Any | None = None) -> Transport:
    """Pick the transport for the resolved config."""
    if config.is_local:
        if store is None:
            raise ValueError("local transport requires an in-process store")
        return DirectTransport(store)
    return HTTPTransport(config)
