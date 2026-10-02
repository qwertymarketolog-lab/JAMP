from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .contract import EvidenceRecord, EvidenceStatus


class EvidenceLedger:
    """Append-oriented evidence store for AEW v0.1.

    Verification is explicit: callers must supply an evidence record already
    carrying VERIFIED status; the ledger never promotes AI output by itself.
    """

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}

    def append(self, record: EvidenceRecord) -> None:
        if record.evidence_id in self._records:
            raise ValueError(f"duplicate evidence_id: {record.evidence_id}")
        self._records[record.evidence_id] = record

    def get(self, evidence_id: str) -> EvidenceRecord:
        return self._records[evidence_id]

    def by_task(self, task_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(r for r in self._records.values() if r.task_id == task_id)

    def by_claim(self, claim_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(r for r in self._records.values() if r.claim_id == claim_id)

    def verified(self, claim_id: str) -> tuple[EvidenceRecord, ...]:
        return tuple(r for r in self.by_claim(claim_id) if r.status is EvidenceStatus.VERIFIED)

    def snapshot(self) -> tuple[EvidenceRecord, ...]:
        return tuple(self._records.values())
