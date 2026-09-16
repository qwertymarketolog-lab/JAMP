"""Research-only EXP-15-R0 Contingency Causality contract tests.

This file defines the boundary between reproducibility and causal inference
without introducing any production API or runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pytest

from jamp.research.canonical import replay_hash
from tests.research.test_contingency_r0 import (
    ContingencyEventR0,
    ContractViolationError,
    EpistemicStatus,
)


class CausalDecisionR0(StrEnum):
    """Research-only result of the EXP-15-R0 causal contract."""

    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class CausalCandidateR0:
    """Minimal research-only causal candidate and its experimental boundary."""

    contingency_ref: str
    hypothesis: str
    control_state: str
    intervention: str
    observed_outcome_control: str
    observed_outcome_intervention: str
    confounders: tuple[str, ...]
    provenance_ref: str
    repeated_observation: bool = False
    replay_successful: bool = False

    def __post_init__(self) -> None:
        required = {
            "contingency_ref": self.contingency_ref,
            "hypothesis": self.hypothesis,
            "control_state": self.control_state,
            "intervention": self.intervention,
            "observed_outcome_control": self.observed_outcome_control,
            "observed_outcome_intervention": self.observed_outcome_intervention,
            "provenance_ref": self.provenance_ref,
        }
        if any(not isinstance(value, str) or not value for value in required.values()):
            raise ContractViolationError("all mandatory CausalCandidate R0 fields are required")
        if not self.contingency_ref.startswith("sha256:"):
            raise ContractViolationError("contingency_ref must be a canonical hash reference")
        if not self.provenance_ref.startswith("sha256:"):
            raise ContractViolationError("provenance_ref must be a canonical hash reference")

    @property
    def differential_outcome(self) -> bool:
        """Return whether intervention and control outcomes differ."""
        return self.observed_outcome_control != self.observed_outcome_intervention


def _hash_ref(payload: object) -> str:
    return f"sha256:{replay_hash(payload)}"


def _contingency() -> ContingencyEventR0:
    return ContingencyEventR0(
        before_state="search-state-0",
        expected_state="search-state-1",
        expected_transition="derive-next-candidate",
        unexpected_observation="candidate diverged from expected transition",
        new_path="search-branch-jump-1",
        provenance_ref=_hash_ref({"event": "exp-15-r0"}),
    )


def _candidate(
    *,
    intervention: str = "disable candidate mechanism",
    control_outcome: str = "baseline",
    intervention_outcome: str = "changed",
    confounders: tuple[str, ...] = (),
    repeated_observation: bool = False,
    replay_successful: bool = False,
) -> CausalCandidateR0:
    event = _contingency()
    return CausalCandidateR0(
        contingency_ref=_hash_ref({"event": event.contingency_event, "event_ref": event.provenance_ref}),
        hypothesis="the intervention changes the observed outcome",
        control_state="mechanism enabled",
        intervention=intervention,
        observed_outcome_control=control_outcome,
        observed_outcome_intervention=intervention_outcome,
        confounders=confounders,
        provenance_ref=_hash_ref({"event": "exp-15-r0-candidate"}),
        repeated_observation=repeated_observation,
        replay_successful=replay_successful,
    )


def evaluate_causal_candidate(candidate: CausalCandidateR0) -> CausalDecisionR0:
    """Apply the research-only EXP-15-R0 causal decision boundary."""
    if candidate.replay_successful and not candidate.differential_outcome:
        return CausalDecisionR0.NOT_SUPPORTED
    if not candidate.intervention:
        return CausalDecisionR0.NOT_SUPPORTED
    if not candidate.differential_outcome:
        return CausalDecisionR0.NOT_SUPPORTED
    if candidate.confounders:
        return CausalDecisionR0.INCONCLUSIVE
    if not candidate.repeated_observation:
        return CausalDecisionR0.INCONCLUSIVE
    return CausalDecisionR0.SUPPORTED


def test_exp15_positive_candidate_has_explicit_intervention_and_difference() -> None:
    candidate = _candidate(
        repeated_observation=True,
        replay_successful=True,
    )

    assert candidate.intervention == "disable candidate mechanism"
    assert candidate.differential_outcome is True


def test_exp15_positive_controlled_intervention_can_reach_supported() -> None:
    candidate = _candidate(
        repeated_observation=True,
        replay_successful=True,
    )

    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.SUPPORTED


def test_exp15_negative_repeated_contingency_is_not_causality() -> None:
    candidate = _candidate(
        repeated_observation=True,
        replay_successful=False,
        intervention="",
    )

    with pytest.raises(ContractViolationError):
        evaluate_causal_candidate(candidate)


def test_exp15_negative_successful_replay_is_not_causality() -> None:
    candidate = _candidate(
        repeated_observation=False,
        replay_successful=True,
    )

    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.INCONCLUSIVE


def test_exp15_negative_correlation_without_intervention_is_not_supported() -> None:
    candidate = _candidate(
        intervention="",
        repeated_observation=True,
    )

    with pytest.raises(ContractViolationError):
        evaluate_causal_candidate(candidate)


def test_exp15_negative_intervention_without_differential_outcome_is_not_supported() -> None:
    candidate = _candidate(
        control_outcome="same",
        intervention_outcome="same",
        repeated_observation=True,
    )

    assert candidate.differential_outcome is False
    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.NOT_SUPPORTED


def test_exp15_negative_untracked_confounder_is_inconclusive() -> None:
    candidate = _candidate(
        confounders=("untracked-environment-change",),
        repeated_observation=True,
    )

    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.INCONCLUSIVE


def test_exp15_negative_single_observation_is_not_automatically_supported() -> None:
    candidate = _candidate(
        repeated_observation=False,
        replay_successful=False,
    )

    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.INCONCLUSIVE


def test_exp15_invariant_replay_does_not_promote_status() -> None:
    candidate = _candidate(
        repeated_observation=False,
        replay_successful=True,
    )

    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.INCONCLUSIVE
    assert evaluate_causal_candidate(candidate) is not CausalDecisionR0.SUPPORTED


def test_exp15_invariant_repetition_without_intervention_does_not_promote_status() -> None:
    candidate = _candidate(
        repeated_observation=True,
        intervention="",
    )

    with pytest.raises(ContractViolationError):
        evaluate_causal_candidate(candidate)


def test_exp15_contingency_event_is_provenance_input_not_causal_status() -> None:
    event = _contingency()
    candidate = _candidate(repeated_observation=False)

    assert event.contingency_event == "CONTINGENCY_EVENT"
    assert event.status is EpistemicStatus.FACT_ABOUT_SEARCH
    assert candidate.provenance_ref.startswith("sha256:")
    assert evaluate_causal_candidate(candidate) is CausalDecisionR0.INCONCLUSIVE
