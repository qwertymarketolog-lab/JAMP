"""Research-only EXP-17-R1 evidence synthesis contract tests.

EXP-17-R1 composes observation metadata and conflict outcomes into aggregate
research metrics without allowing synthesis to promote evidence to SUPPORTED.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EpistemicStatus(Enum):
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class SynthesisInputR1:
    """Inputs consumed by the research-only synthesis layer."""

    observation_confidences: tuple[float, ...]
    divergence_index: float
    conflict_status: EpistemicStatus


@dataclass(frozen=True)
class SynthesisResultR1:
    """Composite metrics plus the guarded epistemic outcome."""

    composite_score: float
    divergence_index: float
    epistemic_status: EpistemicStatus


def synthesize_evidence(data: SynthesisInputR1) -> SynthesisResultR1:
    """Aggregate evidence while preserving the official epistemic guard.

    Composite metrics are descriptive research outputs. They never bypass the
    conflict/evidence contract to promote an input to SUPPORTED automatically.
    """

    if data.observation_confidences:
        composite_score = sum(data.observation_confidences) / len(
            data.observation_confidences
        )
    else:
        composite_score = 0.0

    return SynthesisResultR1(
        composite_score=composite_score,
        divergence_index=data.divergence_index,
        epistemic_status=(
            EpistemicStatus.INCONCLUSIVE
            if data.conflict_status is not EpistemicStatus.SUPPORTED
            else EpistemicStatus.INCONCLUSIVE
        ),
    )


def test_composite_score_is_descriptive_metric() -> None:
    result = synthesize_evidence(
        SynthesisInputR1(
            observation_confidences=(0.8, 0.6),
            divergence_index=0.4,
            conflict_status=EpistemicStatus.INCONCLUSIVE,
        )
    )

    assert result.composite_score == 0.7
    assert result.divergence_index == 0.4


def test_conflict_remains_inconclusive() -> None:
    result = synthesize_evidence(
        SynthesisInputR1(
            observation_confidences=(0.99, 0.98),
            divergence_index=0.01,
            conflict_status=EpistemicStatus.INCONCLUSIVE,
        )
    )

    assert result.epistemic_status is EpistemicStatus.INCONCLUSIVE


def test_synthesis_cannot_auto_promote_to_supported() -> None:
    result = synthesize_evidence(
        SynthesisInputR1(
            observation_confidences=(1.0, 1.0),
            divergence_index=0.0,
            conflict_status=EpistemicStatus.SUPPORTED,
        )
    )

    assert result.composite_score == 1.0
    assert result.epistemic_status is EpistemicStatus.INCONCLUSIVE


def test_empty_observation_set_is_safe() -> None:
    result = synthesize_evidence(
        SynthesisInputR1(
            observation_confidences=(),
            divergence_index=1.0,
            conflict_status=EpistemicStatus.INCONCLUSIVE,
        )
    )

    assert result.composite_score == 0.0
    assert result.epistemic_status is EpistemicStatus.INCONCLUSIVE
