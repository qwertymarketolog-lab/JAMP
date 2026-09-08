"""Pure canonicalization for JAMP research-state hashing.

This module intentionally has no dependency on the JAMP engine, Registry,
CommitManager, or Search Boundary. It accepts plain Python data and frozen
dataclasses and produces deterministic UTF-8 JSON bytes suitable for hashing.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from hashlib import sha256
import json
import math
from typing import Any

# These keys describe execution environment rather than experimental state.
# They are deliberately explicit so provenance cannot silently discard arbitrary
# user data merely because a key happens to contain a timestamp-like value.
_RUNTIME_KEYS = frozenset(
    {
        "execution_timestamp",
        "executed_at",
        "started_at",
        "finished_at",
        "timestamp",
        "runner_id",
        "runner_name",
        "hostname",
        "host",
        "workspace",
        "workspace_path",
        "working_directory",
        "cwd",
        "runtime_metadata",
        "telemetry",
    }
)

_PATH_KEYS = frozenset(
    {
        "path",
        "file_path",
        "absolute_path",
        "workspace_path",
        "working_directory",
        "cwd",
    }
)


def _normalize(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-compatible, deterministic representation of *value*."""
    if is_dataclass(value) and not isinstance(value, type):
        return _normalize(
            {field.name: getattr(value, field.name) for field in fields(value)},
            key=key,
        )

    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise TypeError("canonical state dictionary keys must be strings")
            if raw_key in _RUNTIME_KEYS:
                continue
            if raw_key in _PATH_KEYS and isinstance(raw_value, str):
                # Paths are runtime-dependent metadata. Preserve only the final
                # path component rather than leaking a host-specific prefix.
                raw_value = raw_value.replace("\\", "/").rsplit("/", 1)[-1]
            normalized[raw_key] = _normalize(raw_value, key=raw_key)
        return {name: normalized[name] for name in sorted(normalized)}

    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]

    if isinstance(value, (set, frozenset)):
        items = [_normalize(item) for item in value]
        return sorted(items, key=_sort_key)

    # bool must be checked before int because bool is an int subclass.
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical state cannot contain NaN or infinity")
        # JSON has one numeric representation for zero; eliminate -0.0.
        if value == 0.0:
            return 0
        # Treat integral floats and integers as the same mathematical value.
        if value.is_integer():
            return int(value)
        return value

    raise TypeError(f"unsupported canonical state type: {type(value).__name__}")


def _sort_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_data(state: Any) -> Any:
    """Normalize research state without mutating the caller's object."""
    return _normalize(state)


def canonical_json(state: Any) -> str:
    """Serialize normalized research state using one canonical JSON form."""
    normalized = canonical_data(state)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(state: Any) -> bytes:
    """Return canonical UTF-8 bytes for deterministic hashing."""
    return canonical_json(state).encode("utf-8")


def replay_hash(state: Any) -> str:
    """Return the lowercase SHA-256 digest of canonical research state."""
    return sha256(canonical_bytes(state)).hexdigest()
