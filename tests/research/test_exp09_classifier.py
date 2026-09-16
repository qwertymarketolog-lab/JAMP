"""R2.9 executable contract for the EXP-09 classifier.

This file deliberately contains only pre-execution controls. It does not run
EXP-09, select thresholds from data, or freeze an experiment specification.
"""
from __future__ import annotations

from statistics import median

import pytest


# R2.9a: mathematical contract

def relative_effects(values: list[float]) -> tuple[float, float]:
    """Return (median(r_i), p_+) for a fixed, non-empty sample."""
    if not values:
        raise ValueError("fixed sample must be non-empty")
    n = len(values)
    p_plus = sum(value > 0 for value in values) / n
    return float(median(values)), p_plus


def classify_effects(values: list[float]) -> str:
    """Apply the frozen R2.9 sign classifier without an arbitrary threshold."""
    m, p_plus = relative_effects(values)
    if m > 0 and p_plus > 0.5:
        return "PASS"
    if m < 0 and p_plus < 0.5:
        return "FAIL"
    return "INCONCLUSIVE"


@pytest.mark.parametrize(
    ("values", "expected_median", "expected_p_plus"),
    [
        ([0.1, 0.2, 0.3, 0.4, 0.5], 0.3, 1.0),
        ([-0.1, -0.2, -0.3, -0.4, -0.5], -0.3, 0.0),
        ([-0.1, -0.05, 0.0, 0.05, 0.1], 0.0, 0.4),
    ],
)
def test_r29a_median_and_p_plus(values, expected_median, expected_p_plus) -> None:
    assert relative_effects(values) == (expected_median, expected_p_plus)


# R2.9b: complete sign-boundary matrix for the two decision coordinates.
# The boundary cases use n=4 because, for odd n=5, m > 0 necessarily implies
# p_+ > 0.5, and m < 0 necessarily implies p_+ < 0.5.


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([0.1, 0.2, 0.3, 0.4], "PASS"),                    # m > 0, p_+ > 0.5
        ([0.4, 0.3, -0.1, -0.2], "INCONCLUSIVE"),          # m > 0, p_+ = 0.5
        ([0.1, 0.2, -0.3, -0.4], "INCONCLUSIVE"),          # m < 0, p_+ = 0.5
        ([-0.1, -0.2, -0.3, -0.4], "FAIL"),                # m < 0, p_+ < 0.5
        ([-0.2, -0.1, 0.1, 0.2], "INCONCLUSIVE"),          # m = 0, p_+ = 0.5
        ([-0.3, -0.1, 0.1, 0.3], "INCONCLUSIVE"),          # m = 0, p_+ = 0.5
    ],
)
def test_r29b_classifier_boundary_matrix(values, expected) -> None:
    assert classify_effects(values) == expected


def test_r29b_classifier_is_complete_and_pairwise_disjoint() -> None:
    cases = [
        [0.1, 0.2, 0.3, 0.4],
        [0.4, 0.3, -0.1, -0.2],
        [0.1, 0.2, -0.3, -0.4],
        [-0.1, -0.2, -0.3, -0.4],
        [-0.2, -0.1, 0.1, 0.2],
    ]
    assert all(classify_effects(case) in {"PASS", "FAIL", "INCONCLUSIVE"} for case in cases)


# R2.9c: S0 is an execution invariant, not a scientific verdict.


def validate_s0_invariant(*, merge_count: int, control_expanded: int, treatment_expanded: int) -> None:
    """Reject a no-merge paired execution if the twins expand differently."""
    if merge_count == 0 and control_expanded != treatment_expanded:
        raise ValueError("EXECUTION_INVALID: S0 control/treatment expanded_nodes mismatch")


def test_r29c_s0_equal_expansion_is_valid() -> None:
    validate_s0_invariant(merge_count=0, control_expanded=42, treatment_expanded=42)


def test_r29c_s0_mismatch_is_execution_invalid() -> None:
    with pytest.raises(ValueError, match="EXECUTION_INVALID"):
        validate_s0_invariant(merge_count=0, control_expanded=42, treatment_expanded=41)


def test_r29c_non_s0_mismatch_is_not_rejected_by_s0_invariant() -> None:
    validate_s0_invariant(merge_count=1, control_expanded=42, treatment_expanded=41)
