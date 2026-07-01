"""Sentry-style error fingerprinting (server copy).

Kept byte-for-byte in sync with ``canary.fingerprint`` in the SDK so a group id
computed at capture time equals one recomputed at query time. Duplicated rather
than shared to keep the SDK and server independently installable.
"""

from __future__ import annotations

import hashlib
import re

_NORMALISERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"0x[0-9a-fA-F]+"), "<hex>"),
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "<uuid>"),
    (re.compile(r"(/[^/\s]+)+/?"), "<path>"),
    (re.compile(r"'[^']*'|\"[^\"]*\""), "<str>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"\s+"), " "),
]


def normalize_message(message: str | None) -> str:
    """Reduce an error message to its stable skeleton."""
    if not message:
        return ""
    text = message.strip()
    for pattern, repl in _NORMALISERS:
        text = pattern.sub(repl, text)
    return text.strip().lower()


def fingerprint(
    exception_type: str | None,
    *,
    tool: str | None = None,
    agent: str | None = None,
    message: str | None = None,
) -> str:
    """Return a stable 16-char hex group id for an error."""
    parts = [
        (exception_type or "UnknownError").strip(),
        (tool or "").strip(),
        (agent or "").strip(),
        normalize_message(message),
    ]
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]
