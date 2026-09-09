"""P22.7 deterministic evidence provenance primitives.

Evidence records bind an immutable source/payload observation to a structural
state identity. The ledger is content-addressed and intentionally contains no
decision, ranking, scoring, filtering, confidence, or environment logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from collections.abc import Sequence

__all__ = (
    "EvidenceRecord",
    "EvidenceLedger",
    "build_evidence_ledger",
    "verify_evidence",
)

_SHA256_HEX = 64


def _validate_hash(value: str, name: str) -> str:
    if not isinstance(value, str) or len(value) != _SHA256_HEX:
        raise ValueError(f"{name} must be a lowercase SHA-256 hexadecimal string")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hexadecimal string")
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _evidence_hash(
    source_hash: str, payload_hash: str, state_hash: str, sequence: int
) -> str:
    return hashlib.sha256(
        _canonical_bytes(
            {
                "payload_hash": payload_hash,
                "sequence": sequence,
                "source_hash": source_hash,
                "state_hash": state_hash,
            }
        )
    ).hexdigest()


def _ledger_hash(evidence_hashes: Sequence[str]) -> str:
    return hashlib.sha256(_canonical_bytes(list(evidence_hashes))).hexdigest()


@dataclass(frozen=True, init=False)
class EvidenceRecord:
    evidence_hash: str = field(init=False)
    source_hash: str
    payload_hash: str
    state_hash: str
    sequence: int

    def __init__(
        self,
        source_hash: str,
        payload_hash: str,
        state_hash: str,
        sequence: int,
    ) -> None:
        _validate_hash(source_hash, "source_hash")
        _validate_hash(payload_hash, "payload_hash")
        _validate_hash(state_hash, "state_hash")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise TypeError("sequence must be an integer")
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        object.__setattr__(self, "source_hash", source_hash)
        object.__setattr__(self, "payload_hash", payload_hash)
        object.__setattr__(self, "state_hash", state_hash)
        object.__setattr__(self, "sequence", sequence)
        object.__setattr__(
            self,
            "evidence_hash",
            _evidence_hash(source_hash, payload_hash, state_hash, sequence),
        )

    def export(self) -> dict[str, object]:
        return {
            "evidence_hash": self.evidence_hash,
            "source_hash": self.source_hash,
            "payload_hash": self.payload_hash,
            "state_hash": self.state_hash,
            "sequence": self.sequence,
        }


@dataclass(frozen=True)
class EvidenceLedger:
    records: tuple[EvidenceRecord, ...]
    ledger_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.records, tuple):
            raise TypeError("records must be a tuple")
        _validate_hash(self.ledger_hash, "ledger_hash")
        if any(not isinstance(record, EvidenceRecord) for record in self.records):
            raise TypeError("records must contain only EvidenceRecord instances")
        expected = _ledger_hash([record.evidence_hash for record in self.records])
        if self.ledger_hash != expected:
            raise ValueError("ledger_hash does not match records")

    def export(self) -> dict[str, object]:
        return {
            "records": [record.export() for record in self.records],
            "ledger_hash": self.ledger_hash,
        }


def build_evidence_ledger(records: Sequence[EvidenceRecord]) -> EvidenceLedger:
    if isinstance(records, (str, bytes)):
        raise TypeError("records must be a sequence of EvidenceRecord")
    materialized = tuple(records)
    if any(not isinstance(record, EvidenceRecord) for record in materialized):
        raise TypeError("records must contain only EvidenceRecord instances")
    canonical = tuple(sorted(materialized, key=lambda record: record.sequence))
    for index, record in enumerate(canonical):
        if record.sequence != index:
            raise ValueError("evidence sequences must be contiguous from zero")
    hashes = [record.evidence_hash for record in canonical]
    if len(hashes) != len(set(hashes)):
        raise ValueError("duplicate evidence records are not permitted")
    return EvidenceLedger(canonical, _ledger_hash(hashes))


def verify_evidence(
    ledger: EvidenceLedger, target_state_hash: str | None = None
) -> bool:
    if not isinstance(ledger, EvidenceLedger):
        raise TypeError("ledger must be an EvidenceLedger")
    if target_state_hash is not None:
        _validate_hash(target_state_hash, "target_state_hash")
    expected_hashes: list[str] = []
    for index, record in enumerate(ledger.records):
        if record.sequence != index:
            raise ValueError("evidence sequence mismatch")
        expected = _evidence_hash(
            record.source_hash, record.payload_hash, record.state_hash, record.sequence
        )
        if record.evidence_hash != expected:
            raise ValueError("evidence record integrity mismatch")
        if target_state_hash is not None and record.state_hash != target_state_hash:
            raise ValueError("evidence state binding mismatch")
        expected_hashes.append(expected)
    if ledger.ledger_hash != _ledger_hash(expected_hashes):
        raise ValueError("evidence ledger commitment mismatch")
    return True
