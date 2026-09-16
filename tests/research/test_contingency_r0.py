"""Research-only Contingency R0 contract tests.

This file defines the provisional JUMP/CONTINGENCY_EVENT contract without
introducing any production API or runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pytest

from jamp.research.canonical import replay_hash


class ContractViolationError(ValueError):
    """Raised when a research-only Contingency R0 invariant is violated."""


class EpistemicStatus(StrEnum):
    """Research-only epistemic states used by the Contingency R0 contract."""

    FACT_ABOUT_SEARCH = "FACT_ABOUT_SEARCH"
    INCONCLUSIVE = "INCONCLUSIVE"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class ContingencyEventR0:
    """Minimal research-only representation of a search-trajectory deviation."""

    before_state: str
    expected_state: str
    expected_transition: str
    unexpected_observation: str
    new_path: str
    provenance_ref: str
    controlled_replay: bool = False
    status: EpistemicStatus = EpistemicStatus.FACT_ABOUT_SEARCH

    def __post_init__(self) -> None:
        required = {
            "before_state": self.before_state,
            "expected_state": self.expected_state,
            "expected_transition": self.expected_transition,
            "unexpected_observation": self.unexpected_observation,
            "new_path": self.new_path,
            "provenance_ref": self.provenance_ref,
        }
        if any(not isinstance(value, str) or not value for value in required.values()):
            raise ContractViolationError("all mandatory Contingency R0 fields are required")
        if not self.provenance_ref.startswith("sha256:"):
            raise ContractViolationError("provenance_ref must be a canonical hash reference")
        if self.status is EpistemicStatus.SUPPORTED and not self.controlled_replay:
            raise ContractViolationError("epistemic promotion requires controlled_replay")
        if not self.controlled_replay and self.status is not EpistemicStatus.FACT_ABOUT_SEARCH:
            raise ContractViolationError(
                "without controlled_replay status is limited to FACT_ABOUT_SEARCH"
            )

    @property
    def contingency_event(self) -> str:
        """Return the fixed event kind; it is not itself epistemic evidence."""
        return "CONTINGENCY_EVENT"

    def replay(self, *, reproduced: bool) -> ContingencyEventR0:
        """Apply the research-only controlled-replay boundary."""
        if not reproduced:
            return ContingencyEventR0(
                before_state=self.before_state,
                expected_state=self.expected_state,
                expected_transition=self.expected_transition,
                unexpected_observation=self.unexpected_observation,
                new_path=self.new_path,
                provenance_ref=self.provenance_ref,
                controlled_replay=True,
                status=EpistemicStatus.INCONCLUSIVE,
            )
        return ContingencyEventR0(
            before_state=self.before_state,
            expected_state=self.expected_state,
            expected_transition=self.expected_transition,
            unexpected_observation=self.unexpected_observation,
            new_path=self.new_path,
            provenance_ref=self.provenance_ref,
            controlled_replay=True,
            status=EpistemicStatus.INCONCLUSIVE,
        )


def _provenance_ref(payload: object) -> str:
    return f"sha256:{replay_hash(payload)}"


def _event() -> ContingencyEventR0:
    return ContingencyEventR0(
        before_state="search-state-0",
        expected_state="search-state-1",
        expected_transition="derive-next-candidate",
        unexpected_observation="candidate diverged from expected transition",
        new_path="search-branch-jump-1",
        provenance_ref=_provenance_ref({"event": "contingency-r0"}),
    )


def test_r0_positive_records_expected_and_unexpected_states() -> None:
    event = _event()

    assert event.contingency_event == "CONTINGENCY_EVENT"
    assert event.status is EpistemicStatus.FACT_ABOUT_SEARCH
    assert event.expected_state == "search-state-1"
    assert event.unexpected_observation == "candidate diverged from expected transition"


def test_r0_positive_preserves_provenance_identity() -> None:
    event = _event()

    assert event.provenance_ref == _provenance_ref({"event": "contingency-r0"})


def test_r0_positive_controlled_replay_does_not_auto_promote_to_supported() -> None:
    replayed = _event().replay(reproduced=True)

    assert replayed.controlled_replay is True
    assert replayed.status is EpistemicStatus.INCONCLUSIVE


def test_r0_negative_missing_expected_state() -> None:
    with pytest.raises(
        ContractViolationError,
        match="all mandatory Contingency R0 fields are required",
    ):
        ContingencyEventR0(
            before_state="search-state-0",
            expected_state="",
            expected_transition="derive-next-candidate",
            unexpected_observation="unexpected",
            new_path="branch-1",
            provenance_ref=_provenance_ref({"event": "missing-expected-state"}),
        )


def test_r0_negative_broken_provenance() -> None:
    with pytest.raises(ContractViolationError, match="canonical hash reference"):
        ContingencyEventR0(
            before_state="search-state-0",
            expected_state="search-state-1",
            expected_transition="derive-next-candidate",
            unexpected_observation="unexpected",
            new_path="branch-1",
            provenance_ref="broken-reference",
        )


def test_r0_negative_randomness_cannot_be_declared_supported() -> None:
    with pytest.raises(ContractViolationError, match="requires controlled_replay"):
        ContingencyEventR0(
            before_state="search-state-0",
            expected_state="search-state-1",
            expected_transition="derive-next-candidate",
            unexpected_observation="unexpected",
            new_path="branch-1",
            provenance_ref=_provenance_ref({"event": "unsupported-promotion"}),
            status=EpistemicStatus.SUPPORTED,
        )


def test_r0_negative_epistemic_promotion_without_replay_is_rejected() -> None:
    with pytest.raises(ContractViolationError, match="requires controlled_replay"):
        ContingencyEventR0(
            before_state="search-state-0",
            expected_state="search-state-1",
            expected_transition="derive-next-candidate",
            unexpected_observation="unexpected",
            new_path="branch-1",
            provenance_ref=_provenance_ref({"event": "implicit-promotion"}),
            status=EpistemicStatus.SUPPORTED,
        )


def test_r0_negative_unreproduced_replay_remains_inconclusive() -> None:
    replayed = _event().replay(reproduced=False)

    assert replayed.controlled_replay is True
    assert replayed.status is EpistemicStatus.INCONCLUSIVE


def test_r0_invariant_contingency_is_not_evidence() -> None:
    event = _event()

    assert event.contingency_event == "CONTINGENCY_EVENT"
    assert event.status is not EpistemicStatus.SUPPORTED
