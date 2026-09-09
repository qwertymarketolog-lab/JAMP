"""P22.9 hypothesis scoring contract.

Contract-first diagnostic: this module intentionally targets an absent
implementation.  The tests define the deterministic scoring boundary,
evidence requirement, and multi-criteria aggregation surface.
"""

import pytest

from jamp.research import hypothesis_scoring as scoring



def test_score_is_normalized_at_lower_boundary():
    assert scoring.score_hypothesis(criteria=(0.0,)) == 0.0


def test_score_is_normalized_at_upper_boundary():
    assert scoring.score_hypothesis(criteria=(1.0,)) == 1.0


@pytest.mark.parametrize("value", [-1.0, 1.000001, 2.0])
def test_score_rejects_out_of_bounds(value):
    with pytest.raises(ValueError):
        scoring.score_hypothesis(criteria=(value,))


def test_score_requires_evidence_backing():
    with pytest.raises(ValueError, match="evidence"):
        scoring.score_hypothesis(criteria=(0.5,), evidence_refs=())


def test_score_accepts_evidence_backed_hypothesis():
    assert scoring.score_hypothesis(
        criteria=(0.5,), evidence_refs=("evidence-hash",)
    ) == 0.5


def test_multi_criteria_aggregation_is_deterministic():
    assert scoring.score_hypothesis(
        criteria=(0.2, 0.4, 0.8), evidence_refs=("evidence-hash",)
    ) == pytest.approx((0.2 + 0.4 + 0.8) / 3.0)


def test_multi_criteria_requires_each_value_in_range():
    with pytest.raises(ValueError):
        scoring.score_hypothesis(
            criteria=(0.2, 1.1, 0.8), evidence_refs=("evidence-hash",)
        )


def test_scoring_is_repeatable():
    kwargs = {"criteria": (0.25, 0.75), "evidence_refs": ("evidence-hash",)}
    assert scoring.score_hypothesis(**kwargs) == scoring.score_hypothesis(**kwargs)


def test_public_boundary_is_explicit():
    assert set(scoring.__all__) == {"score_hypothesis"}
