"""Research-only EXP-18 R2.1 canonical audit export."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

_FORBIDDEN_KEYS = frozenset({"score", "confidence", "rank", "voting_weight"})
_SCHEMA_VERSION = "r2.1"


@dataclass(frozen=True)
class AuditExport:
    """Canonical audit representation of an R1 projection."""

    bytes_payload: bytes
    manifest_hash: str
    manifest: dict[str, Any]


def _canonical_value(value: Any) -> Any:
    """Convert supported values into deterministic JSON-compatible values."""
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported audit value type: {type(value).__name__}")


def _record_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("object_ref", "")),
        str(item.get("property", "")),
        str(item.get("provenance", "")),
        json.dumps(
            _canonical_value(item.get("value")),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    )


def _canonical_records(view: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    records = [_canonical_value(item) for item in view]
    if not all(isinstance(item, dict) for item in records):
        raise TypeError("Audit view must contain mapping records")
    for item in records:
        if _FORBIDDEN_KEYS.intersection(item):
            raise ValueError("Audit view contains forbidden scoring metadata")
    return sorted(records, key=_record_key)


def _canonical_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _assert_no_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = _FORBIDDEN_KEYS.intersection(value)
        if forbidden:
            raise ValueError(f"Forbidden scoring metadata: {sorted(forbidden)}")
        for child in value.values():
            _assert_no_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_forbidden_keys(child)


def export_audit_manifest(
    view: tuple[dict[str, Any], ...],
) -> AuditExport:
    """Export an R1 view as deterministic, non-scoring audit bytes."""
    records = _canonical_records(view)
    manifest: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "records": records,
    }
    _assert_no_forbidden_keys(manifest)
    payload = _canonical_bytes(manifest)
    return AuditExport(
        bytes_payload=payload,
        manifest_hash=hashlib.sha256(payload).hexdigest(),
        manifest=manifest,
    )


def parse_audit_manifest(payload: bytes) -> tuple[dict[str, Any], ...]:
    """Parse canonical audit bytes back into an R1-equivalent projection."""
    if not isinstance(payload, bytes):
        raise TypeError("Audit manifest payload must be bytes")

    manifest = json.loads(payload.decode("utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("Unsupported audit manifest schema")
    _assert_no_forbidden_keys(manifest)

    records = manifest.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("Invalid audit manifest records")

    return tuple(records)
