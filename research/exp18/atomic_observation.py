from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

ALLOWED_TYPES = frozenset({"text_token", "semantic_chunk", "structural_node"})


@dataclass(frozen=True)
class AtomicObservation:
    id: str
    content: str
    type: str
    source_ref: str
    source_id: str
    subject: str
    event: str
    value: str
    confidence: float
    provenance: dict[str, Any]
    parent_link: dict[str, Any]


class AtomicObservationError(ValueError):
    """Invalid EXP-18 atomic observation."""


def create_atomic_observation(
    *,
    content: str,
    atom_type: str,
    source_ref: str,
    operator_id: str,
    operator_version: str,
    params: dict[str, Any],
    source_id: str = "",
    subject: str = "",
    event: str = "",
    value: str = "",
    confidence: float = 1.0,
    parent_id: str | None = None,
) -> AtomicObservation:
    if not source_ref:
        raise AtomicObservationError("source_ref is required")
    if not operator_id or not operator_version:
        raise AtomicObservationError("operator id and version are required")
    if atom_type not in ALLOWED_TYPES:
        raise AtomicObservationError(f"unsupported atom type: {atom_type}")
    if not 0.0 <= confidence <= 1.0:
        raise AtomicObservationError("confidence must be between 0.0 and 1.0")

    provenance = {
        "input_hash": source_ref,
        "operator": {
            "id": operator_id,
            "version": operator_version,
        },
        "params": params,
    }
    parent_link = {
        "root_hash": source_ref,
        "parent_id": parent_id,
    }
    identity_payload = {
        "input": source_ref,
        "operator": provenance["operator"],
        "params": params,
        "content": content,
        "type": atom_type,
        "source_id": source_id,
        "subject": subject,
        "event": event,
        "value": value,
        "confidence": confidence,
        "parent_link": parent_link,
    }
    canonical = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    atom_id = hashlib.sha256(canonical).hexdigest()

    return AtomicObservation(
        id=atom_id,
        content=content,
        type=atom_type,
        source_ref=source_ref,
        source_id=source_id,
        subject=subject,
        event=event,
        value=value,
        confidence=confidence,
        provenance=provenance,
        parent_link=parent_link,
    )
