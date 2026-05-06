"""Privacy-preserving helpers for observability."""

from __future__ import annotations

import hashlib


def hash_text(value: str) -> str:
    """Return a stable short hash for text without logging the text itself."""
    normalized = " ".join(value.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
