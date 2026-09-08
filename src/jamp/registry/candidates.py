"""JAMP Candidate Evaluation and Provenance Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class VerificationStatus(Enum):
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


@dataclass
class Candidate:
    candidate_id: str
    statement: str
    source_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Provenance:
    source_id: str
    rule_applied: str
    evidence_id: Optional[str]
    event_id: str
    fingerprint: str


@dataclass
class VerificationResult:
    candidate: Candidate
    status: VerificationStatus
    provenance: Optional[Provenance] = None
