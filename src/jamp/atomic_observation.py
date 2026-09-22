"""EXP-22 v0 atomic observation identity implementation.

This module implements the locked EXP-22 v0 identity contract without
modifying the JAMP run loop.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


CANONICAL_DELIMITER = "||"
SCHEMA_VERSION = "v0"

ALLOWED_ID_PARAMS = {"segment_index", "span_start", "span_end"}

FORBIDDEN_SEMANTIC_KEYS = {
    "verdict",
    "supported",
    "rejected",
    "confidence",
}


def _validate_semantic_neutrality(value: Any) -> None:
    """Reject evaluation verdict fields anywhere in an input structure."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and key.lower() in FORBIDDEN_SEMANTIC_KEYS:
                raise ValueError(f"forbidden semantic key: {key!r}")
            _validate_semantic_neutrality(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _validate_semantic_neutrality(nested)


def _canonical_json(value: Any) -> str:
    """Serialize a JSON-compatible value according to the locked v0 rules."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value is not canonically JSON-serializable") from exc


def _extract_closed_identity_params(params: dict[str, Any]) -> dict[str, Any]:
    """Return only the closed structural parameter subset."""
    return {
        key: params[key]
        for key in sorted(params.keys())
        if key in ALLOWED_ID_PARAMS and params[key] is not None
    }


def compute_canonical_preimage(
    source_ref: str,
    atom_type: str,
    operator_id: str,
    operator_version: str,
    content: Any,
    params: dict[str, Any],
) -> str:
    """Build the exact seven-component EXP-22 v0 identity preimage."""
    if not isinstance(source_ref, str) or not source_ref:
        raise ValueError("source_ref must be a non-empty string")
    for name, value in (
        ("atom_type", atom_type),
        ("operator_id", operator_id),
        ("operator_version", operator_version),
    ):
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
    if not isinstance(params, dict):
        raise ValueError("params must be a dictionary")

    _validate_semantic_neutrality(content)
    _validate_semantic_neutrality(params)

    filtered_params = _extract_closed_identity_params(params)

    parts = [
        SCHEMA_VERSION,
        source_ref,
        atom_type,
        operator_id,
        operator_version,
        _canonical_json(content),
        _canonical_json(filtered_params),
    ]
    return CANONICAL_DELIMITER.join(parts)


@dataclass(frozen=True)
class AtomicObservation:
    """Immutable v0 observation envelope with deterministic identity."""

    id: str
    source_ref: str
    atom_type: str
    operator_id: str
    operator_version: str
    content: Any
    params: dict[str, Any]


def create_atomic_observation(
    *,
    content: Any,
    atom_type: str,
    source_ref: str,
    operator_id: str,
    operator_version: str,
    params: dict[str, Any],
) -> AtomicObservation:
    """Create an EXP-22 v0 atomic observation."""
    preimage = compute_canonical_preimage(
        source_ref,
        atom_type,
        operator_id,
        operator_version,
        content,
        params,
    )
    observation_id = hashlib.sha256(preimage.encode("utf-8")).hexdigest()

    return AtomicObservation(
        id=observation_id,
        source_ref=source_ref,
        atom_type=atom_type,
        operator_id=operator_id,
        operator_version=operator_version,
        content=content,
        params=params,
    )


__all__ = [
    "ALLOWED_ID_PARAMS",
    "AtomicObservation",
    "CANONICAL_DELIMITER",
    "FORBIDDEN_SEMANTIC_KEYS",
    "SCHEMA_VERSION",
    "compute_canonical_preimage",
    "create_atomic_observation",
]
