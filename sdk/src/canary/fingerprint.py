"""Sentry-style error fingerprinting.

Two failures belong to the same *group* when they share an exception type, the
tool they happened in, and the agent that was running — even if the exact
message text differs (ids, timestamps, paths vary run to run). We normalise the
message to strip that variable noise, then hash the stable parts.

This module is intentionally dependency-free so both the SDK (at capture time)
and the backend (at query time) can compute identical fingerprints.
"""

from __future__ import annotations

import hashlib
import re

# Order matters: collapse the most specific patterns first.
_NORMALISERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"0x[0-9a-fA-F]+"), "<hex>"),                       # memory addrs / hex ids
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"    # uuids
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "<uuid>"),
    (re.compile(r"(/[^/\s]+)+/?"), "<path>"),                        # filesystem paths
    (re.compile(r"'[^']*'|\"[^\"]*\""), "<str>"),                  # quoted literals
    (re.compile(r"\d+(?:\.\d+)?"), "<n>"),                          # numbers (incl. "12ms", "3.14")
    (re.compile(r"\s+"), " "),                                       # whitespace runs
]


def normalize_message(message: str | None) -> str:
    """Reduce an error message to its stable skeleton.

    ``"Timeout after 3021ms calling 'search' at /tmp/x.py:42"`` and
    ``"Timeout after 5ms calling 'search' at /var/y.py:9"`` both normalise to
    the same string, so they fingerprint together.
    """

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
    """Return a stable 16-char hex group id for an error.

    Grouping key = exception type + tool + agent + normalised message. The
    message is included so genuinely different failures inside the same tool
    (e.g. ``KeyError`` vs a validation message) don't collapse together, while
    the normalisation keeps near-identical messages in one group.
    """

    parts = [
        (exception_type or "UnknownError").strip(),
        (tool or "").strip(),
        (agent or "").strip(),
        normalize_message(message),
    ]
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]
