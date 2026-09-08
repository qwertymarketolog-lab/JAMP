"""Minimal JAMP Next verification core.

The engine separates generation from verification. A candidate is never
considered verified merely because a generator proposed it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class Status(str, Enum):
    CONFIRMED = "CONFIRMED"
    DERIVED = "DERIVED"
    HYPOTHESIS = "HYPOTHESIS"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Evidence:
    source_id: str
    statement: str
    supports: bool = True
    confidence: float = 1.0


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    statement: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationResult:
    candidate: Candidate
    status: Status
    evidence: tuple[Evidence, ...] = ()
    reason: str = ""


class JAMPVerifier:
    """Small deterministic verifier used by adapters and experiments."""

    def verify(self, candidate: Candidate, evidence: Iterable[Evidence]) -> VerificationResult:
        items = tuple(evidence)
        positive = tuple(e for e in items if e.supports)
        negative = tuple(e for e in items if not e.supports)

        if positive and negative:
            status = Status.CONFLICT
            reason = "Supporting and contradicting evidence are both present."
        elif positive:
            status = Status.CONFIRMED
            reason = "At least one supporting evidence item is present."
        elif negative:
            status = Status.CONFLICT
            reason = "Available evidence contradicts the candidate."
        else:
            status = Status.UNKNOWN
            reason = "No evidence was supplied."

        return VerificationResult(candidate, status, items, reason)
