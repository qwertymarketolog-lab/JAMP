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


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_invalid_ai_probability_refuses(inputs: dict[str, Any], value: float) -> None:
    raw = {"ai_generated_probability": value, "human_performance_probability": 0.2}
    result = call(inputs, lambda *_: raw)
    assert result.status == REFUSE
    assert result.raw_output is raw


def test_empty_model_output_is_inconclusive(inputs: dict[str, Any]) -> None:
    result = call(inputs, lambda *_: {})
    assert result.status == INCONCLUSIVE


def test_success_preserves_raw_output_and_provenance(inputs: dict[str, Any]) -> None:
    raw = {
        "ai_generated_probability": 0.91,
        "human_performance_probability": 0.07,
        "vendor_trace": {"token": "unchanged"},
    }
    result = call(inputs, lambda *_: raw)
    assert result.status == VERIFIED
    assert result.raw_output is raw
    assert result.metrics == {
        "ai_generated_probability": 0.91,
        "human_performance_probability": 0.07,
    }
    assert result.target_sha256 == inputs["expected_target_sha256"]
    assert result.weights_sha256 == inputs["expected_weights_sha256"]
    assert result.model_id == "test-model"
    assert result.model_version == "1"
