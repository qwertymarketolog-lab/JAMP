"""Optional transport adapter into the standard JAMP AtomicObservation envelope."""
from __future__ import annotations

from typing import Any

from jamp.atomic_observation import AtomicObservation, create_atomic_observation

from .identity import JAMP1CAtom


def to_jamp_envelope(atom: JAMP1CAtom) -> AtomicObservation:
    """Wrap a JAMP-1C atom without replacing its domain identity."""
    content: dict[str, Any] = {
        "jamp_1c_id": atom.id,
        "payload": atom.content,
        "context": atom.context,
    }
    return create_atomic_observation(
        content=content,
        atom_type="jamp_1c_" + atom.atom_type,
        source_ref=atom.source_ref,
        operator_id=atom.operator_id,
        operator_version=atom.operator_version,
        params={"segment_index": 0},
    )
