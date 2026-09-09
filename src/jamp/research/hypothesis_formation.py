"""P22.8 deterministic hypothesis formation primitives.

Hypotheses are immutable, content-addressed propositions grounded in the
P22.7 evidence ledger. This module performs structural validation only.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from . import canonical
from .evidence import EvidenceLedger, EvidenceRecord, verify_evidence

__all__ = (
    "Hypothesis",
    "HypothesisSet",
    "build_hypothesis_set",
    "verify_hypothesis_provenance",
)

_SHA256_HEX = 64


def _validate_hash(value: str, name: str) -> str:
    if not isinstance(value, str) or len(value) != _SHA256_HEX:
        raise ValueError(f"{name} must be a lowercase SHA-256 hexadecimal string")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hexadecimal string")
    return value


def _hypothesis_digest(
    evidence_refs: tuple[str, ...],
    state_hash: str,
    proposition: str,
    sequence: int,
) -> str:
    return canonical.replay_hash(
        {
            "evidence_refs": list(evidence_refs),
            "proposition": proposition,
            "sequence": sequence,
            "state_hash": state_hash,
        }
    )


def _set_digest(hypotheses: tuple["Hypothesis", ...]) -> str:
    return canonical.replay_hash([item.hypothesis_hash for item in hypotheses])


@dataclass(frozen=True, init=False)
class Hypothesis:
    hypothesis_hash: str = field(init=False)
    evidence_refs: tuple[str, ...]
    state_hash: str
    proposition: str
    sequence: int

    def __init__(
        self,
        evidence_refs: tuple[str, ...],
        state_hash: str,
        proposition: str,
        sequence: int,
    ) -> None:
        if not isinstance(evidence_refs, tuple):
            raise TypeError("evidence_refs must be a tuple")
        if not evidence_refs:
            raise ValueError("hypothesis must reference evidence")
        for reference in evidence_refs:
            _validate_hash(reference, "evidence_refs item")
        _validate_hash(state_hash, "state_hash")
        if not isinstance(proposition, str):
            raise TypeError("proposition must be a string")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise TypeError("sequence must be an integer")
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "state_hash", state_hash)
        object.__setattr__(self, "proposition", proposition)
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(
            self,
            "hypothesis_hash",
            _hypothesis_digest(evidence_refs, state_hash, proposition, sequence),
        )

    def export(self) -> dict[str, object]:
        return {
            "hypothesis_hash": self.hypothesis_hash,
            "evidence_refs": list(self.evidence_refs),
            "state_hash": self.state_hash,
            "proposition": self.proposition,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class HypothesisSet:
    hypotheses: tuple[Hypothesis, ...]
    set_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.hypotheses, tuple):
            raise TypeError("hypotheses must be a tuple")
        if any(not isinstance(item, Hypothesis) for item in self.hypotheses):
            raise TypeError("hypotheses must contain only Hypothesis instances")
        _validate_hash(self.set_hash, "set_hash")
        expected = _set_digest(self.hypotheses)
        if self.set_hash != expected:
            raise ValueError("set_hash does not match hypotheses")

    def export(self) -> dict[str, object]:
        return {
            "hypotheses": [item.export() for item in self.hypotheses],
            "set_hash": self.set_hash,
        }


def _evidence_map(ledger: EvidenceLedger) -> dict[str, EvidenceRecord]:
    return {record.evidence_hash: record for record in ledger.records}


def build_hypothesis_set(
    hypotheses: Sequence[Hypothesis], ledger: EvidenceLedger
) -> HypothesisSet:
    if isinstance(hypotheses, (str, bytes)):
        raise TypeError("hypotheses must be a sequence of Hypothesis")
    if not isinstance(ledger, EvidenceLedger):
        raise TypeError("ledger must be an EvidenceLedger")
    verify_evidence(ledger)
    materialized = tuple(hypotheses)
    if any(not isinstance(item, Hypothesis) for item in materialized):
        raise TypeError("hypotheses must contain only Hypothesis instances")

    evidence_by_hash = _evidence_map(ledger)
    by_sequence: list[Hypothesis | None] = [None] * len(materialized)
    hashes: set[str] = set()
    for item in materialized:
        if item.sequence >= len(materialized):
            raise ValueError("hypothesis sequences must be contiguous from zero")
        if by_sequence[item.sequence] is not None:
            raise ValueError("duplicate hypothesis sequences are not permitted")
        if item.hypothesis_hash in hashes:
            raise ValueError("duplicate hypothesis records are not permitted")
        hashes.add(item.hypothesis_hash)
        for reference in item.evidence_refs:
            record = evidence_by_hash.get(reference)
            if record is None:
                raise ValueError("hypothesis references missing evidence")
            if record.state_hash != item.state_hash:
                raise ValueError("hypothesis state grounding mismatch")
        by_sequence[item.sequence] = item

    canonical_hypotheses = tuple(item for item in by_sequence if item is not None)
    if len(canonical_hypotheses) != len(materialized):
        raise ValueError("hypothesis sequences must be contiguous from zero")
    return HypothesisSet(canonical_hypotheses, _set_digest(canonical_hypotheses))


def verify_hypothesis_provenance(
    hypothesis_set: HypothesisSet, ledger: EvidenceLedger
) -> bool:
    if not isinstance(hypothesis_set, HypothesisSet):
        raise TypeError("hypothesis_set must be a HypothesisSet")
    if not isinstance(ledger, EvidenceLedger):
        raise TypeError("ledger must be an EvidenceLedger")
    verify_evidence(ledger)
    expected_set_hash = _set_digest(hypothesis_set.hypotheses)
    if hypothesis_set.set_hash != expected_set_hash:
        raise ValueError("hypothesis set commitment mismatch")
    evidence_by_hash = _evidence_map(ledger)
    for index, item in enumerate(hypothesis_set.hypotheses):
        if item.sequence != index:
            raise ValueError("hypothesis sequence mismatch")
        expected_hash = _hypothesis_digest(
            item.evidence_refs, item.state_hash, item.proposition, item.sequence
        )
        if item.hypothesis_hash != expected_hash:
            raise ValueError("hypothesis integrity mismatch")
        for reference in item.evidence_refs:
            record = evidence_by_hash.get(reference)
            if record is None:
                raise ValueError("hypothesis references missing evidence")
            if record.state_hash != item.state_hash:
                raise ValueError("hypothesis state grounding mismatch")
    return True
