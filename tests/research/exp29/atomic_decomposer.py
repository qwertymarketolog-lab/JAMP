"""Pure atomic projection for EXP-29."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AtomicObservation:
    """One provenance-preserving atomic projection of an EXP-28 observation."""

    observation_id: str
    source_ref: str
    zero_index: int
    real_part: float
    imag_part: float
    metadata: tuple[tuple[str, Any], ...]


def decompose(observation: dict[str, Any], source_ref: str) -> AtomicObservation:
    """Project one raw observation without adding semantic claims."""
    metadata = tuple(sorted(dict(observation["metadata"]).items()))
    return AtomicObservation(
        observation_id=source_ref,
        source_ref=source_ref,
        zero_index=observation["zero_index"],
        real_part=observation["real_part"],
        imag_part=observation["imag_part"],
        metadata=metadata,
    )


def decompose_all(
    observations: tuple[dict[str, Any], ...],
    source_refs: tuple[str, ...],
) -> tuple[AtomicObservation, ...]:
    if len(observations) != len(source_refs):
        raise ValueError("observations and source_refs must have equal length")
    return tuple(
        decompose(observation, ref)
        for observation, ref in zip(observations, source_refs, strict=True)
    )


def reconstruct(atom: AtomicObservation) -> dict[str, Any]:
    """Reconstruct only fields present in the source observation."""
    return {
        "zero_index": atom.zero_index,
        "real_part": atom.real_part,
        "imag_part": atom.imag_part,
        "metadata": dict(atom.metadata),
    }


def has_semantic_claim(atom: AtomicObservation) -> bool:
    """Guard against semantic fields entering the atomic representation."""
    return any(key in {"claim", "interpretation"} for key, _ in atom.metadata)
