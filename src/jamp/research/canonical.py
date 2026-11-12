"""P19.1 canonical serialization and replay hashing primitives.

Research-only module. Canonical bytes follow RFC 8785 (JSON Canonicalization
Scheme) so independently implemented consumers derive the same digest.

Migration note: replacing the legacy json.dumps serializer can change bytes
(and therefore SHA-256 identities) for values involving ECMAScript number
formatting or UTF-16 object-key ordering. Previously persisted hashes derived
from the legacy serializer must be recomputed before they are treated as
verified. Stage B manifest identity remains provisional until re-derived
under this RFC 8785 implementation and independently verified.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import jcs


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
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError("canonical object keys must be strings")
            normalized[key] = _normalize(item)
        return normalized
    raise CanonicalizationError(f"unsupported value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Return RFC 8785 canonical JSON encoded as UTF-8 bytes."""
    normalized = _normalize(value)
    try:
        canonical_output = jcs.canonicalize(normalized)
        if isinstance(canonical_output, bytes):
            return canonical_output
        if isinstance(canonical_output, str):
            return canonical_output.encode("utf-8")
        raise TypeError("jcs.canonicalize must return str or bytes")
    except Exception as exc:
        if isinstance(exc, CanonicalizationError):
            raise
        raise CanonicalizationError(
            "value cannot be represented as RFC 8785 canonical JSON"
        ) from exc


def replay_hash(value: Any) -> str:
    """Return the SHA-256 digest of RFC 8785 canonical state bytes."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


__all__ = ("CanonicalizationError", "canonical_bytes", "replay_hash")
