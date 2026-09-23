"""JAMP engine package."""

from dataclasses import dataclass
from typing import Any

from ..adapters import Generator, KnowledgeSource
from ..core import JAMPVerifier, Status, VerificationResult
from ..registry import Registry
from .commit import CommitManager
from .evaluate import VerificationEngine
from ..events.dag import EventDAG
from ..registry.candidates import (
    Candidate as CommitCandidate,
    Provenance,
    VerificationResult as CommitVerificationResult,
    VerificationStatus,
)


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    payload: dict[str, Any]


class _LegacyRegistryView(Registry):
    """Compatibility view for the original JAMPEngine API/tests.

    The authoritative Registry still stores modern ``fact``/``conflict`` records.
    The legacy engine historically exposed confirmed candidates as
    ``verified_candidate`` and did not expose conflicts through ``all()``.
    """

    def by_kind(self, kind: str):
        if kind == "verified_candidate":
            kind = "fact"
        return super().by_kind(kind)

    def all(self):
        return tuple(record for record in super().all() if record.kind != "conflict")


class JAMPEngine:
    def __init__(self, generator: Generator, knowledge: KnowledgeSource) -> None:
        self.generator = generator
        self.knowledge = knowledge
        self.verifier = JAMPVerifier()
        self.registry = _LegacyRegistryView()
        self.dag = EventDAG()
        self.commit_manager = CommitManager(self.registry, self.dag)
        self.history: list[Event] = []
        self._counter = 0

    def _event(self, event_type: str, **payload: Any) -> Event:
        self._counter += 1
        event = Event(f"E{self._counter}", event_type, payload)
        self.history.append(event)
        return event

    def _commit_legacy_result(self, result: VerificationResult) -> None:
        """Adapt the legacy verifier result to the authoritative commit gateway."""
        candidate = result.candidate
        source_id = result.evidence[0].source_id if result.evidence else "legacy_unknown"

        status_map = {
            Status.CONFIRMED: VerificationStatus.CONFIRMED,
            Status.CONFLICT: VerificationStatus.CONFLICT,
            Status.UNKNOWN: VerificationStatus.UNKNOWN,
        }
        status = status_map.get(result.status)
        if status is None:
            # DERIVED/HYPOTHESIS are not authoritative fact states in the new gateway.
            return

        # The legacy engine's conflict behavior was "do not commit". Keep that
        # public behavior while the new JAMPPipeline uses explicit conflict records.
        if status is VerificationStatus.CONFLICT:
            return

        provenance = None
        if status is VerificationStatus.CONFIRMED:
            import hashlib

            fingerprint = hashlib.sha256(
                f"{candidate.candidate_id}:{candidate.statement}".encode()
            ).hexdigest()
            provenance = Provenance(
                source_id=source_id,
                rule_applied="LEGACY_EVIDENCE_MATCH",
                evidence_id=source_id,
                event_id="EVT_0001",
                fingerprint=fingerprint,
            )

        self.commit_manager.commit(
            CommitVerificationResult(
                candidate=CommitCandidate(
                    candidate_id=candidate.candidate_id,
                    statement=candidate.statement,
                    source_id=source_id,
                    metadata=candidate.metadata,
                ),
                status=status,
                provenance=provenance,
            )
        )

    def run(self, prompt: str) -> list[VerificationResult]:
        candidates = tuple(self.generator.generate(prompt))
        self._event("GENERATE", prompt=prompt, count=len(candidates))
        results: list[VerificationResult] = []

        for candidate in candidates:
            self._event("EVALUATE", candidate_id=candidate.candidate_id)
            evidence = tuple(self.knowledge.search(candidate.statement))
            result = self.verifier.verify(candidate, evidence)
            results.append(result)
            self._event(
                "VERIFIED",
                candidate_id=candidate.candidate_id,
                status=result.status.value,
            )

            self._commit_legacy_result(result)
            if result.status in {Status.CONFIRMED, Status.DERIVED}:
                self._event("COMMIT", candidate_id=candidate.candidate_id)

        return results


__all__ = ["Event", "JAMPEngine", "VerificationEngine"]
