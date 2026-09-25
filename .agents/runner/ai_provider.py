"""Provider-agnostic AI proposal contract for Autonomous Research Loop v0.

AI output is an observation/proposal only. It is never evidence, authorization,
a decision, a state transition, or merge authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from evidence import Evidence
from operation_policy import Operation, Target, TargetKind
from task_loader import TaskContract, path_allowed

PROTOCOL_VERSION: Final = "AI-PROVIDER-V0"
FORBIDDEN_CLAIMS: Final = frozenset({"VERIFIED", "PASS", "GREEN", "MERGE_ALLOWED"})


class AIProviderError(ValueError):
    """Raised when an AI provider request or response violates the v0 contract."""


class AIProviderUnavailable(RuntimeError):
    """Raised when the provider cannot produce a response."""


@dataclass(frozen=True)
class AIObservation:
    kind: str
    value: str
    source: str


@dataclass(frozen=True)
class VerifiedEvidence:
    workflow: str
    run_id: str
    job_id: str | None
    status: str
    conclusion: str
    artifact_id: str | None
    scope: str


@dataclass(frozen=True)
class AIRequest:
    protocol_version: str
    request_id: str
    task: TaskContract
    objective: str
    runner_state: str
    previous_action: str | None
    iteration: int
    source_sha: str
    base_sha: str | None
    observations: tuple[AIObservation, ...] = ()
    verified_evidence: tuple[VerifiedEvidence, ...] = ()


@dataclass(frozen=True)
class AIProposal:
    protocol_version: str
    request_id: str
    provider_id: str
    model_id: str
    model_request_id: str
    hypothesis: str
    observation_summary: str
    proposed_operation: Operation
    target: Target
    expected_effect: str
    confidence: float
    claimed_state: str | None = None


@dataclass(frozen=True)
class AIProvider:
    """Minimal v0 provider boundary; concrete providers implement generate."""

    provider_id: str
    model_id: str

    def generate(self, request: AIRequest) -> AIProposal:
        raise NotImplementedError


def validate_request(request: AIRequest) -> None:
    if not isinstance(request, AIRequest):
        raise AIProviderError("request must be AIRequest")
    if request.protocol_version != PROTOCOL_VERSION:
        raise AIProviderError("unsupported protocol version")
    if not request.request_id.strip():
        raise AIProviderError("request_id is required")
    if not request.task.task_id:
        raise AIProviderError("task_id is required")
    if not request.source_sha.strip():
        raise AIProviderError("source_sha is required")
    if not request.objective.strip():
        raise AIProviderError("objective is required")
    if not request.runner_state.strip():
        raise AIProviderError("runner_state is required")
    if request.iteration < 0:
        raise AIProviderError("iteration must be non-negative")
    if request.task.allowed_paths is None or request.task.forbidden_paths is None:
        raise AIProviderError("malformed task scope")
    if not all(isinstance(p, str) and p for p in request.task.allowed_paths):
        raise AIProviderError("malformed task scope")
    if not all(isinstance(p, str) and p for p in request.task.forbidden_paths):
        raise AIProviderError("malformed task scope")


def validate_proposal(request: AIRequest, proposal: AIProposal) -> None:
    validate_request(request)
    if not isinstance(proposal, AIProposal):
        raise AIProviderError("response must be AIProposal")
    if proposal.protocol_version != PROTOCOL_VERSION:
        raise AIProviderError("unsupported protocol version")
    if proposal.request_id != request.request_id:
        raise AIProviderError("request_id mismatch")
    if not proposal.provider_id.strip() or not proposal.model_id.strip():
        raise AIProviderError("provider/model identity is required")
    if not proposal.model_request_id.strip():
        raise AIProviderError("model_request_id is required")
    if not proposal.hypothesis.strip() or not proposal.observation_summary.strip():
        raise AIProviderError("proposal text is required")
    if not proposal.expected_effect.strip():
        raise AIProviderError("expected_effect is required")
    if not 0.0 <= proposal.confidence <= 1.0:
        raise AIProviderError("confidence must be in [0, 1]")
    if proposal.claimed_state is not None and proposal.claimed_state.upper() in FORBIDDEN_CLAIMS:
        raise AIProviderError("AI state claims are not authoritative")
    try:
        operation = Operation(proposal.proposed_operation)
    except (TypeError, ValueError) as exc:
        raise AIProviderError("unsupported operation") from exc
    if not isinstance(proposal.target, Target):
        raise AIProviderError("invalid target")
    if operation in (Operation.WRITE, Operation.DELETE):
        if proposal.target.kind is not TargetKind.PATH:
            raise AIProviderError("path operation requires PATH target")
        if proposal.target.value.startswith("src/jamp/") or proposal.target.value == "src/jamp":
            raise AIProviderError("Frozen Core mutation rejected")
        if not path_allowed(request.task, proposal.target.value):
            raise AIProviderError("target is outside task scope")
    elif operation is Operation.PUSH:
        if proposal.target.kind is not TargetKind.REF or proposal.target.value in {
            "main",
            "refs/heads/main",
        }:
            raise AIProviderError("main mutation rejected")
    elif operation is Operation.MERGE:
        raise AIProviderError("AI has no merge authority")
    elif operation is not Operation.READ:
        raise AIProviderError("unsupported operation")


def proposal_evidence(evidence: Evidence | None) -> Evidence:
    if evidence is None or not evidence.source_sha or not evidence.task_id:
        raise AIProviderError("missing evidence: INCONCLUSIVE")
    return evidence


__all__ = [
    "AIObservation",
    "AIProvider",
    "AIProviderError",
    "AIProviderUnavailable",
    "AIProposal",
    "AIRequest",
    "PROTOCOL_VERSION",
    "VerifiedEvidence",
    "proposal_evidence",
    "validate_proposal",
    "validate_request",
]
