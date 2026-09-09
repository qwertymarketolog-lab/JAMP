"""P19.1 canonical serialization and replay hashing primitives.

Research-only module.  The serializer deliberately strips runtime-specific
representation and rejects non-finite floating point values.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented canonically."""


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("NaN and Infinity are not canonical values")
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            if not isinstance(key, str):
                raise CanonicalizationError("canonical object keys must be strings")
            normalized[key] = _normalize(value[key])
        return normalized
    raise CanonicalizationError(f"unsupported value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a supported value."""
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def replay_hash(value: Any) -> str:
    """Return the SHA-256 digest of canonical state bytes."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()
