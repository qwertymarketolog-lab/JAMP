import pytest

from jamp.research.prediction import (
    ExpectedDirection,
    PredictionIntegrityError,
    PredictionRecord,
    compute_prediction_hash,
)

HYPOTHESIS_REF = "09bf8a49822ac51d91b2fbed861082a881ad0696d19572d0caeb19aafbdee242"
TARGET_METRIC = "expanded_nodes"
EXPECTED_DIRECTION = ExpectedDirection.DECREASE
EXPECTED_HASH = "18adbdda4fbe7f114f8062d3ec1d1948c33635448a4f414e4aa7a17661befec7"


def make_record() -> PredictionRecord:
    return PredictionRecord(
        hypothesis_ref=HYPOTHESIS_REF,
        target_metric=TARGET_METRIC,
        expected_direction=EXPECTED_DIRECTION,
        prediction_hash=EXPECTED_HASH,
    )


def test_canonical_bytes_are_deterministic() -> None:
    first = make_record()
    second = make_record()
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.prediction_hash == second.prediction_hash == EXPECTED_HASH


def test_canonical_bytes_match_the_declared_hash_material() -> None:
    record = make_record()
    assert compute_prediction_hash(
        record.hypothesis_ref,
        record.target_metric,
        record.expected_direction,
    ) == EXPECTED_HASH


def test_each_mutable_input_changes_content_hash() -> None:
    assert (
        compute_prediction_hash(
            HYPOTHESIS_REF,
            "expanded_edges",
            EXPECTED_DIRECTION,
        )
        != EXPECTED_HASH
    )
    assert (
        compute_prediction_hash(
            HYPOTHESIS_REF,
            TARGET_METRIC,
            ExpectedDirection.INCREASE,
        )
        != EXPECTED_HASH
    )
    other_hypothesis = "0" * 64
    assert (
        compute_prediction_hash(
            other_hypothesis,
            TARGET_METRIC,
            EXPECTED_DIRECTION,
        )
        != EXPECTED_HASH
    )


def test_missing_prediction_hash_is_rejected() -> None:
    with pytest.raises(TypeError):
        PredictionRecord(  # type: ignore[call-arg]
            hypothesis_ref=HYPOTHESIS_REF,
            target_metric=TARGET_METRIC,
            expected_direction=EXPECTED_DIRECTION,
        )


def test_invalid_reference_is_rejected() -> None:
    with pytest.raises(PredictionIntegrityError, match="hypothesis_ref"):
        PredictionRecord(
            hypothesis_ref="latest",
            target_metric=TARGET_METRIC,
            expected_direction=EXPECTED_DIRECTION,
            prediction_hash=EXPECTED_HASH,
        )


def test_hash_mismatch_is_rejected() -> None:
    with pytest.raises(PredictionIntegrityError, match="prediction_hash"):
        PredictionRecord(
            hypothesis_ref=HYPOTHESIS_REF,
            target_metric=TARGET_METRIC,
            expected_direction=EXPECTED_DIRECTION,
            prediction_hash="0" * 64,
        )


def test_runtime_metadata_cannot_enter_target_metric() -> None:
    with pytest.raises(PredictionIntegrityError):
        PredictionRecord(
            hypothesis_ref=HYPOTHESIS_REF,
            target_metric="expanded nodes",
            expected_direction=EXPECTED_DIRECTION,
            prediction_hash=EXPECTED_HASH,
        )


def test_record_is_frozen() -> None:
    record = make_record()
    with pytest.raises(AttributeError):
        record.target_metric = "expanded_edges"  # type: ignore[misc]
