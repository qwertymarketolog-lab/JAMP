from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"
    CONTRADICTED = "CONTRADICTED"


class ResearchState(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    HYPOTHESIS_FORMED = "HYPOTHESIS_FORMED"
    EXPERIMENT_DEFINED = "EXPERIMENT_DEFINED"
    RUNNING = "RUNNING"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    VERIFIED = "VERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class WorkerObservation:
    worker_id: str
    provider: str
    model: str
    task_id: str
    input_hash: str
    observations: Sequence[str] = ()
    hypotheses: Sequence[str] = ()
    proposed_experiments: Sequence[str] = ()
    uncertainties: Sequence[str] = ()
    output_hash: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    task_id: str
    claim_id: str
    source_type: str
    source_id: str
    commit_sha: str | None = None
    workflow: str | None = None
    run_id: int | None = None
    job_id: int | None = None
    artifact_id: int | None = None
    raw_hash: str | None = None
    observed_at: str | None = None
    scope: str | None = None
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    metadata: Mapping[str, Any] = field(default_factory=dict)


class AIWorker(Protocol):
    worker_id: str
    provider: str
    model: str

    def observe(self, task: Mapping[str, Any], context: Mapping[str, Any]) -> WorkerObservation: ...
    def hypothesize(self, observations: Sequence[WorkerObservation]) -> WorkerObservation: ...
    def propose_experiment(self, hypothesis: WorkerObservation) -> WorkerObservation: ...
    def review(self, evidence: Sequence[EvidenceRecord]) -> WorkerObservation: ...
    def conclude(self, evidence: Sequence[EvidenceRecord]) -> WorkerObservation: ...
