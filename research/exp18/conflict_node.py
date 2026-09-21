"""Research-only EXP-18 Phase #4 ConflictNode v0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CollisionType(StrEnum):
    AGREEMENT = "AGREEMENT"
    CONFLICT = "CONFLICT"


class EpistemicStatus(StrEnum):
    AGREEMENT = "AGREEMENT"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class AtomicObservation:
    object_ref: str
    property: str
    val_curr: Any
    provenance: str

    def __post_init__(self) -> None:
        if not self.object_ref or not self.property or not self.provenance:
            raise ValueError("AtomicObservation identity and provenance must be non-empty")


@dataclass(frozen=True)
class ConflictResult:
    status: EpistemicStatus
    collision: CollisionType | None
    discrepancies: tuple[dict[str, Any], ...]
    provenance: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provenance:
            raise ValueError("ConflictResult provenance must be non-empty")


def _atom_key(atom: AtomicObservation) -> tuple[str, str]:
    return atom.object_ref, atom.property


def classify(sources: tuple[tuple[AtomicObservation, ...], ...]) -> ConflictResult:
    """Classify independently supplied atoms without selecting a source as truth.

    Missing comparable atoms and conflicting values both remain INCONCLUSIVE.
    A CONFLICT collision is retained explicitly in the collision field.
    """

    if not sources or any(not source for source in sources):
        provenance = tuple(
            sorted(atom.provenance for source in sources for atom in source if atom.provenance)
        )
        return ConflictResult(
            status=EpistemicStatus.INCONCLUSIVE,
            collision=None,
            discrepancies=(),
            provenance=provenance,
        )

    by_source = [{_atom_key(atom): atom for atom in source} for source in sources]
    all_keys = set().union(*(source.keys() for source in by_source))
    discrepancies: list[dict[str, Any]] = []

    for key in sorted(all_keys):
        observations = [source.get(key) for source in by_source]
        if any(atom is None for atom in observations):
            discrepancies.append(
                {
                    "object_ref": key[0],
                    "property": key[1],
                    "reason": "MISSING_COMPARABLE_ATOM",
                }
            )
            continue

        values = {repr(atom.val_curr) for atom in observations if atom is not None}
        if len(values) > 1:
            discrepancies.append(
                {
                    "object_ref": key[0],
                    "property": key[1],
                    "reason": "VALUE_MISMATCH",
                    "values": tuple(sorted(values)),
                }
            )

    provenance = tuple(
        sorted(atom.provenance for source in sources for atom in source if atom.provenance)
    )
    if discrepancies:
        return ConflictResult(
            status=EpistemicStatus.INCONCLUSIVE,
            collision=CollisionType.CONFLICT,
            discrepancies=tuple(discrepancies),
            provenance=provenance,
        )

    return ConflictResult(
        status=EpistemicStatus.AGREEMENT,
        collision=CollisionType.AGREEMENT,
        discrepancies=(),
        provenance=provenance,
    )
