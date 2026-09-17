"""Research-only EXP-17-R0 evidence conflict contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from jamp.research.canonical import replay_hash


class EpistemicStatus(StrEnum):
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class EvidenceRecordR0:
    source_id: str
    observation: str
    provenance_ref: str

    def __post_init__(self) -> None:
        if not self.source_id or not self.observation or not self.provenance_ref:
            raise ValueError("EvidenceRecord fields must be non-empty")

    def canonical(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "observation": self.observation,
            "provenance_ref": self.provenance_ref,
        }


@dataclass(frozen=True)
class EvidenceConflictR0:
    left: EvidenceRecordR0
    right: EvidenceRecordR0

    def canonical(self) -> dict[str, Any]:
        return {
            "left": self.left.canonical(),
            "right": self.right.canonical(),
            "conflict": True,
        }

    @property
    def provenance_ref(self) -> str:
        return replay_hash(self.canonical())


def reconcile_conflict(conflict: EvidenceConflictR0) -> EpistemicStatus:
    """A source conflict is recorded, not resolved by automatic promotion."""
    _ = conflict
    return EpistemicStatus.INCONCLUSIVE


def test_exp17_conflicting_sources_are_preserved() -> None:
    left = EvidenceRecordR0(
        source_id="cv-observation-x",
        observation="object-x",
        provenance_ref="prov-x",
    )
    right = EvidenceRecordR0(
        source_id="other-observation-y",
        observation="object-y",
        provenance_ref="prov-y",
    )

    conflict = EvidenceConflictR0(left=left, right=right)

    assert conflict.left.observation != conflict.right.observation
    assert conflict.canonical()["conflict"] is True
    assert conflict.provenance_ref


def test_exp17_conflict_does_not_auto_promote_either_source() -> None:
    conflict = EvidenceConflictR0(
        left=EvidenceRecordR0(
            source_id="cv-observation-x",
            observation="object-x",
            provenance_ref="prov-x",
        ),
        right=EvidenceRecordR0(
            source_id="other-observation-y",
            observation="object-y",
            provenance_ref="prov-y",
        ),
    )

    assert reconcile_conflict(conflict) is EpistemicStatus.INCONCLUSIVE
    assert reconcile_conflict(conflict) is not EpistemicStatus.SUPPORTED


def test_exp17_conflict_provenance_changes_when_source_evidence_changes() -> None:
    left = EvidenceRecordR0(
        source_id="cv-observation-x",
        observation="object-x",
        provenance_ref="prov-x",
    )
    right_a = EvidenceRecordR0(
        source_id="other-observation-y",
        observation="object-y",
        provenance_ref="prov-y",
    )
    right_b = EvidenceRecordR0(
        source_id="other-observation-y",
        observation="object-z",
        provenance_ref="prov-z",
    )

    first = EvidenceConflictR0(left=left, right=right_a)
    second = EvidenceConflictR0(left=left, right=right_b)

    assert first.provenance_ref != second.provenance_ref
