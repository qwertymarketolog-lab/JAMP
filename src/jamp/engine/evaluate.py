"""JAMP Adversarial Verification Engine."""

import hashlib
from typing import Dict

from jamp.registry.candidates import (
    Candidate,
    Provenance,
    VerificationResult,
    VerificationStatus,
)


class VerificationEngine:
    def __init__(self, knowledge_base: Dict[str, bool]):
        self.knowledge_base = knowledge_base
        self.event_counter = 0

    def verify_candidate(self, candidate: Candidate) -> VerificationResult:
        statement = candidate.statement

        if candidate.metadata.get("is_contradictory", False):
            status = VerificationStatus.CONFLICT
            provenance = None
        elif statement in self.knowledge_base:
            if self.knowledge_base[statement] is True:
                status = VerificationStatus.CONFIRMED
                self.event_counter += 1
                raw_hash = (
                    f"{candidate.source_id}:{statement}:{self.event_counter}"
                ).encode("utf-8")
                fingerprint = hashlib.sha256(raw_hash).hexdigest()
                provenance = Provenance(
                    source_id=candidate.source_id,
                    rule_applied="KB_EXACT_MATCH",
                    evidence_id=(
                        f"EVID_{hashlib.md5(statement.encode()).hexdigest()[:8]}"
                    ),
                    event_id=f"EVT_{self.event_counter:04d}",
                    fingerprint=fingerprint,
                )
            else:
                status = VerificationStatus.REJECTED
                provenance = None
        else:
            status = VerificationStatus.UNKNOWN
            provenance = None

        return VerificationResult(
            candidate=candidate,
            status=status,
            provenance=provenance,
        )
