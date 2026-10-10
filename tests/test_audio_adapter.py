from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from jamp.audio.adapter import HOLD, INCONCLUSIVE, REFUSE, VERIFIED, analyze


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, Any]:
    target = tmp_path / "target.mp3"
    target.write_bytes(b"test media bytes")
    weights = tmp_path / "weights.bin"
    weights.write_bytes(b"trusted weights")
    return {
        "target_path": target,
        "expected_target_sha256": digest(target.read_bytes()),
        "weights_path": weights,
        "expected_weights_sha256": digest(weights.read_bytes()),
        "model_id": "test-model",
        "model_version": "1",
        "tool_id": "test-analyzer",
        "tool_version": "1.2.3",
        "analyzed_at": "2026-10-10T19:00:00Z",
    }


def call(inputs: dict[str, Any], infer: Any):
    return analyze(**inputs, infer=infer)


def test_missing_weights_holds_without_inference(inputs: dict[str, Any]) -> None:
    inputs["weights_path"] = Path(inputs["weights_path"]).with_name("missing.bin")
    invoked = False

    def infer(*_args: Any) -> Any:
        nonlocal invoked
        invoked = True
        return {}

    result = call(inputs, infer)
    assert result.status == HOLD
    assert result.reason == "weights_missing"
    assert not invoked


def test_invalid_weights_hash_holds_without_inference(inputs: dict[str, Any]) -> None:
    inputs["expected_weights_sha256"] = "0" * 64
    invoked = False

    def infer(*_args: Any) -> Any:
        nonlocal invoked
        invoked = True
        return {}

    result = call(inputs, infer)
    assert result.status == HOLD
    assert result.reason == "weights_sha256_mismatch"
    assert not invoked


def test_target_hash_mismatch_refuses_without_inference(inputs: dict[str, Any]) -> None:
    inputs["expected_target_sha256"] = "0" * 64
    invoked = False

    def infer(*_args: Any) -> Any:
        nonlocal invoked
        invoked = True
        return {}

    result = call(inputs, infer)
    assert result.status == REFUSE
    assert result.reason == "target_sha256_mismatch"
    assert not invoked


@pytest.mark.parametrize(
    "metric_key",
    ["synthetic_probability", "human_performance_probability", "confidence_score"],
)
@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_normalized_probability_refuses(
    inputs: dict[str, Any], metric_key: str, value: float
) -> None:
    raw = {
        "synthetic_probability": 0.7,
        "human_performance_probability": 0.2,
        "confidence_score": 0.9,
        "detected_artifacts": [],
    }
    raw[metric_key] = value
    result = call(inputs, lambda *_: raw)
    assert result.status == REFUSE
    assert result.raw_output is raw


def test_empty_model_output_is_inconclusive(inputs: dict[str, Any]) -> None:
    result = call(inputs, lambda *_: {})
    assert result.status == INCONCLUSIVE


def test_inference_receives_exact_verified_bytes_even_if_paths_change(
    inputs: dict[str, Any],
) -> None:
    target_path = Path(inputs["target_path"])
    weights_path = Path(inputs["weights_path"])
    expected_target = target_path.read_bytes()
    expected_weights = weights_path.read_bytes()

    def infer(target_bytes: bytes, weights_bytes: bytes) -> dict[str, Any]:
        assert target_bytes == expected_target
        assert weights_bytes == expected_weights
        target_path.write_bytes(b"changed after verification")
        weights_path.write_bytes(b"changed weights after verification")
        return {
            "synthetic_probability": 0.91,
            "human_performance_probability": 0.07,
            "confidence_score": 0.95,
            "detected_artifacts": [],
        }

    result = call(inputs, infer)
    assert result.status == VERIFIED
    assert result.target_sha256 == digest(expected_target)
    assert result.weights_sha256 == digest(expected_weights)
    assert target_path.read_bytes() != expected_target
    assert weights_path.read_bytes() != expected_weights


def test_missing_analyzer_provenance_is_not_verified(inputs: dict[str, Any]) -> None:
    inputs["tool_version"] = ""
    invoked = False

    def infer(*_args: Any) -> Any:
        nonlocal invoked
        invoked = True
        return {
            "synthetic_probability": 0.5,
            "human_performance_probability": 0.5,
            "confidence_score": 0.5,
            "detected_artifacts": [],
        }

    result = call(inputs, infer)
    assert result.status == INCONCLUSIVE
    assert result.reason == "analyzer_provenance_incomplete"
    assert not invoked


def test_invalid_analyzer_timestamp_is_not_verified(inputs: dict[str, Any]) -> None:
    inputs["analyzed_at"] = "not-a-timestamp"
    result = call(
        inputs,
        lambda *_: {
            "synthetic_probability": 0.5,
            "human_performance_probability": 0.5,
            "confidence_score": 0.5,
            "detected_artifacts": [],
        },
    )
    assert result.status == INCONCLUSIVE
    assert result.reason == "analyzer_timestamp_invalid"


def test_success_preserves_raw_output_metrics_and_provenance(
    inputs: dict[str, Any],
) -> None:
    raw = {
        "synthetic_probability": 0.91,
        "human_performance_probability": 0.07,
        "confidence_score": 0.95,
        "detected_artifacts": ["fixture_artifact"],
        "vendor_trace": {"token": "unchanged"},
    }
    result = call(inputs, lambda *_: raw)
    assert result.status == VERIFIED
    assert result.raw_output is raw
    assert result.metrics == {
        "synthetic_probability": 0.91,
        "human_performance_probability": 0.07,
        "confidence_score": 0.95,
        "detected_artifacts": ["fixture_artifact"],
    }
    assert result.target_sha256 == inputs["expected_target_sha256"]
    assert result.weights_sha256 == inputs["expected_weights_sha256"]
    assert result.model_id == "test-model"
    assert result.model_version == "1"
    assert result.provenance == {
        "tool_id": "test-analyzer",
        "tool_version": "1.2.3",
        "model_version": "1",
        "analyzed_at": "2026-10-10T19:00:00Z",
    }
