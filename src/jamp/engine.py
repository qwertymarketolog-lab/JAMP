"""Orchestration layer for GENERATE -> EVALUATE -> COMMIT."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .adapters import Generator, KnowledgeSource
from .core import Candidate, JAMPVerifier, Status, VerificationResult
from .registry import Registry, RegistryRecord


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: str
    payload: dict[str, Any]


class JAMPEngine:
    def __init__(self, generator: Generator, knowledge: KnowledgeSource) -> None:
        self.generator = generator
        self.knowledge = knowledge
        self.verifier = JAMPVerifier()
        self.registry = Registry()
        self.history: list[Event] = []
        self._counter = 0

    def _event(self, event_type: str, **payload: Any) -> Event:
        self._counter += 1
        event = Event(f"E{self._counter}", event_type, payload)
        self.history.append(event)
        return event

    def run(self, prompt: str) -> list[VerificationResult]:
        candidates = tuple(self.generator.generate(prompt))
        self._event("GENERATE", prompt=prompt, count=len(candidates))
        results: list[VerificationResult] = []

        for candidate in candidates:
            self._event("EVALUATE", candidate_id=candidate.candidate_id)
            evidence = tuple(self.knowledge.search(candidate.statement))
            result = self.verifier.verify(candidate, evidence)
            results.append(result)
            self._event("VERIFIED", candidate_id=candidate.candidate_id, status=result.status.value)

            if result.status in {Status.CONFIRMED, Status.DERIVED}:
                self.registry.add(
                    RegistryRecord(
                        record_id=candidate.candidate_id,
                        kind="verified_candidate",
                        payload={
                            "statement": candidate.statement,
                            "status": result.status.value,
                            "evidence": [e.source_id for e in result.evidence],
                        },
                    )
                )
                self._event("COMMIT", candidate_id=candidate.candidate_id)

        return results
