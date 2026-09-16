"""Research-only EXP-16-R0 Contingency -> Evidence contract tests.

This file defines the boundary between causal experimental results and an
immutable evidence record without introducing new production APIs or runtime
behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from jamp.research.canonical import replay_hash
from jamp.research.evidence import EvidenceRecord, build_evidence_ledger, verify_evidence
from tests.research.test_contingency_causality_r0 import (
    CausalCandidateR0,
    CausalDecisionR0,
    _candidate,
)


class EvidenceDecisionR0(StrEnum):
    """Research-only epistemic boundary for an evidence record."""

    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class EvidenceRecordR0:
    """Immutable research record binding causal evidence to provenance."""

    contingency_ref: str
    causal_candidate_ref: str
    intervention: str
    control_outcome: str
    intervention_outcome: str
    repeated_observation: bool
    confounders: tuple[str, ...]
    evidence_ref: str
    epistemic_status: EvidenceDecisionR0

    def __post_init__(self) -> None:
        required = {
            "contingency_ref": self.contingency_ref,
            "causal_candidate_ref": self.causal_candidate_ref,
            "intervention": self.intervention,
            "control_outcome": self.control_outcome,
            "intervention_outcome": self.intervention_outcome,
            "evidence_ref": self.evidence_ref,
        }
        if any(not isinstance(value, str) or not value for value in required.values()):
            raise ValueError("all EvidenceRecord R0 identity fields are required")
        if not self.contingency_ref.startswith("sha256:"):
            raise ValueError("contingency_ref must be a canonical hash reference")
        if not self.causal_candidate_ref.startswith("sha256:"):
            raise ValueError("causal_candidate_ref must be a canonical hash reference")
        if not self.evidence_ref.startswith("sha256:"):
            raise ValueError("evidence_ref must be a canonical hash reference")
        if not isinstance(self.repeated_observation, bool):
            raise TypeError("repeated_observation must be boolean")
        if not isinstance(self.confounders, tuple):
            raise TypeError("confounders must be a tuple")
        if not isinstance(self.epistemic_status, EvidenceDecisionR0):
            raise TypeError("epistemic_status must use EvidenceDecisionR0")

    @property
    def differential_outcome(self) -> bool:
        return self.control_outcome != self.intervention_outcome

    def canonical_payload(self) -> dict[str, object]:
        return {
            "causal_candidate_ref": self.causal_candidate_ref,
            "confounders": self.confounders,
            "contingency_ref": self.contingency_ref,
            "control_outcome": self.control_outcome,
            "epistemic_status": self.epistemic_status.value,
            "evidence_ref": self.evidence_ref,
            "intervention": self.intervention,
            "intervention_outcome": self.intervention_outcome,
            "repeated_observation": self.repeated_observation,
        }


def _hash_ref(payload: object) -> str:
    return f"sha256:{replay_hash(payload)}"


def _candidate_ref(candidate: CausalCandidateR0) -> str:
    return _hash_ref(
        {
            "contingency_ref": candidate.contingency_ref,
            "hypothesis": candidate.hypothesis,
            "intervention": candidate.intervention,
            "control": candidate.observed_outcome_control,
            "intervention_outcome": candidate.observed_outcome_intervention,
        }
    )


def evaluate_evidence_r0(candidate: CausalCandidateR0) -> EvidenceDecisionR0:
    """Convert a causal result to evidence status without promoting replay alone."""
    causal_status = __import__(
        "tests.research.test_contingency_causality_r0", fromlist=["evaluate_causal_candidate"]
    ).evaluate_causal_candidate(candidate)
    if causal_status is CausalDecisionR0.NOT_SUPPORTED:
        return EvidenceDecisionR0.NOT_SUPPORTED
    if causal_status is CausalDecisionR0.INCONCLUSIVE:
        return EvidenceDecisionR0.INCONCLUSIVE
    return EvidenceDecisionR0.SUPPORTED


def freeze_evidence(candidate: CausalCandidateR0) -> EvidenceRecordR0:
    """Create an immutable research evidence record from a causal candidate."""
    status = evaluate_evidence_r0(candidate)
    contingency_ref = candidate.contingency_ref
    candidate_ref = _candidate_ref(candidate)
    payload = {
        "causal_candidate_ref": candidate_ref,
        "contingency_ref": contingency_ref,
        "control_outcome": candidate.observed_outcome_control,
        "confounders": candidate.confounders,
        "epistemic_status": status.value,
        "intervention": candidate.intervention,
        "intervention_outcome": candidate.observed_outcome_intervention,
        "repeated_observation": candidate.repeated_observation,
    }
    return EvidenceRecordR0(
        contingency_ref=contingency_ref,
        causal_candidate_ref=candidate_ref,
        intervention=candidate.intervention,
        control_outcome=candidate.observed_outcome_control,
        intervention_outcome=candidate.observed_outcome_intervention,
        repeated_observation=candidate.repeated_observation,
        confounders=candidate.confounders,
        evidence_ref=_hash_ref(payload),
        epistemic_status=status,
    )


def test_exp16_positive_controlled_causal_result_becomes_supported_evidence() -> None:
    candidate = _candidate(repeated_observation=True, replay_successful=True)

    evidence = freeze_evidence(candidate)

    assert evidence.epistemic_status is EvidenceDecisionR0.SUPPORTED
    assert evidence.differential_outcome is True
    assert evidence.contingency_ref == candidate.contingency_ref


def test_exp16_evidence_preserves_full_provenance_boundary() -> None:
    candidate = _candidate(repeated_observation=True)
    evidence = freeze_evidence(candidate)

    assert evidence.contingency_ref.startswith("sha256:")
    assert evidence.causal_candidate_ref.startswith("sha256:")
    assert evidence.evidence_ref.startswith("sha256:")


def test_exp16_replay_only_remains_inconclusive() -> None:
    candidate = _candidate(repeated_observation=False, replay_successful=True)

    evidence = freeze_evidence(candidate)

    assert evidence.epistemic_status is EvidenceDecisionR0.INCONCLUSIVE


def test_exp16_repetition_without_intervention_is_not_supported() -> None:
    candidate = _candidate(intervention="", repeated_observation=True)

    evidence = freeze_evidence(candidate)

    assert evidence.epistemic_status is EvidenceDecisionR0.NOT_SUPPORTED


def test_exp16_intervention_without_differential_outcome_is_not_supported() -> None:
    candidate = _candidate(
        control_outcome="same",
        intervention_outcome="same",
        repeated_observation=True,
    )

    evidence = freeze_evidence(candidate)

    assert evidence.differential_outcome is False
    assert evidence.epistemic_status is EvidenceDecisionR0.NOT_SUPPORTED


def test_exp16_unresolved_confounder_is_inconclusive() -> None:
    candidate = _candidate(
        confounders=("untracked-environment-change",),
        repeated_observation=True,
    )

    evidence = freeze_evidence(candidate)

    assert evidence.epistemic_status is EvidenceDecisionR0.INCONCLUSIVE


def test_exp16_single_observation_is_inconclusive() -> None:
    candidate = _candidate(repeated_observation=False, replay_successful=False)

    evidence = freeze_evidence(candidate)

    assert evidence.epistemic_status is EvidenceDecisionR0.INCONCLUSIVE


def test_exp16_replay_does_not_promote_an_evidence_record() -> None:
    candidate = _candidate(repeated_observation=False, replay_successful=True)
    first = freeze_evidence(candidate)
    second = freeze_evidence(candidate)

    assert first == second
    assert first.epistemic_status is EvidenceDecisionR0.INCONCLUSIVE


def test_exp16_evidence_record_is_immutable() -> None:
    candidate = _candidate(repeated_observation=True)
    evidence = freeze_evidence(candidate)

    try:
        evidence.epistemic_status = EvidenceDecisionR0.SUPPORTED
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("EvidenceRecord R0 must be immutable")


def test_exp16_evidence_identity_changes_when_payload_changes() -> None:
    candidate = _candidate(repeated_observation=True)
    original = freeze_evidence(candidate)
    changed_candidate = _candidate(
        intervention="disable different mechanism",
        repeated_observation=True,
    )
    changed = freeze_evidence(changed_candidate)

    assert original.evidence_ref != changed.evidence_ref


def test_exp16_existing_production_evidence_ledger_verifies_research_binding() -> None:
    candidate = _candidate(repeated_observation=True)
    evidence = freeze_evidence(candidate)
    source_hash = evidence.contingency_ref.removeprefix("sha256:")
    payload_hash = replay_hash(evidence.canonical_payload())
    state_hash = replay_hash({"epistemic_status": evidence.epistemic_status.value})
    production_record = EvidenceRecord(source_hash, payload_hash, state_hash, 0)
    ledger = build_evidence_ledger((production_record,))

    assert verify_evidence(ledger) is True


def test_exp16_conflicting_evidence_is_not_silently_resolved() -> None:
    candidate = _candidate(repeated_observation=True)
    first = freeze_evidence(candidate)
    conflicting = EvidenceRecordR0(
        contingency_ref=first.contingency_ref,
        causal_candidate_ref=first.causal_candidate_ref,
        intervention=first.intervention,
        control_outcome=first.control_outcome,
        intervention_outcome="conflicting-result",
        repeated_observation=first.repeated_observation,
        confounders=first.confounders,
        evidence_ref=_hash_ref({"conflict": True, "source": first.evidence_ref}),
        epistemic_status=EvidenceDecisionR0.INCONCLUSIVE,
    )

    assert conflicting.evidence_ref != first.evidence_ref
    assert conflicting.intervention_outcome != first.intervention_outcome
    assert conflicting.epistemic_status is EvidenceDecisionR0.INCONCLUSIVE


def test_exp16_status_is_not_derived_from_evidence_hash() -> None:
    candidate = _candidate(repeated_observation=False, replay_successful=True)
    evidence = freeze_evidence(candidate)

    assert evidence.evidence_ref
    assert evidence.epistemic_status is EvidenceDecisionR0.INCONCLUSIVE
    assert evidence.evidence_ref != f"sha256:{replay_hash(evidence.epistemic_status.value)}"
