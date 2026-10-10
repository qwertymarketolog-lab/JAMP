"""Executable tests for the Audio/Video Evidence v0.1 fixtures.

The gate helper is a test reference, not production runtime behavior. The conflict
policy is test-only because the contract leaves its threshold to a separately
versioned policy.
"""
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "audio-video-evidence-v0.1.schema.json"
VECTORS_PATH = ROOT / "test-vectors" / "audio-video-evidence-v0.1.json"
CONFLICT_POLICY_VERSION = "test-sign-disagreement-v1"
REQUIRED_METRICS = {
    "synthetic_probability",
    "human_performance_probability",
    "confidence_score",
    "detected_artifacts",
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vectors() -> dict[str, dict[str, Any]]:
    payload = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["vectors"]}


def fixture_schema_errors(
    instance: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Check schema constraints exercised by these five deterministic vectors.

    This focused checker avoids adding a new dependency and is not a general
    JSON Schema implementation.
    """
    errors: list[str] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("unexpected schema dialect")
    if not isinstance(instance, dict):
        return ["root must be an object"]
    if set(instance) - set(schema.get("properties", {})):
        errors.append("unknown top-level property")
    for key in schema.get("required", []):
        if key not in instance:
            errors.append(f"missing top-level property: {key}")
    if instance.get("contract_version") != "jamp-audio-video-evidence-v0.1":
        errors.append("invalid contract_version")

    anchor = instance.get("target_anchor")
    if isinstance(anchor, dict):
        required_anchor = ("sha256", "size_bytes", "media_type", "format")
        if not all(key in anchor for key in required_anchor):
            errors.append("target_anchor missing required property")
        media_type = anchor.get("media_type")
        if media_type == "audio":
            media_required = ("duration_ms", "audio")
        elif media_type == "video":
            media_required = ("duration_ms", "video")
        else:
            media_required = ()
        if not media_required or not all(key in anchor for key in media_required):
            errors.append("target_anchor media metadata incomplete")
        if media_type == "audio" and "video" in anchor:
            errors.append("audio anchor contains video metadata")
        if media_type == "video" and "audio" in anchor:
            errors.append("video anchor contains audio metadata")
        digest = anchor.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append("invalid target anchor digest shape")

    results = instance.get("analysis_results")
    if not isinstance(results, list) or not results:
        errors.append("analysis_results must be a non-empty array")
        return errors

    for index, result in enumerate(results):
        prefix = f"analysis_results[{index}]"
        if not isinstance(result, dict):
            errors.append(f"{prefix} must be an object")
            continue
        allowed_result = {"analyzer", "target_sha256", "metrics"}
        if set(result) - allowed_result:
            errors.append(f"{prefix} contains unknown property")
        if not all(key in result for key in allowed_result):
            errors.append(f"{prefix} missing required property")
        digest = result.get("target_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append(f"{prefix} has invalid target digest shape")

        analyzer = result.get("analyzer")
        required_analyzer = (
            "tool_id",
            "tool_version",
            "model_version",
            "analyzed_at",
        )
        if not isinstance(analyzer, dict) or not all(
            key in analyzer for key in required_analyzer
        ):
            errors.append(f"{prefix} analyzer provenance incomplete")

        metrics = result.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{prefix} metrics must be an object")
            continue
        if set(metrics) - (REQUIRED_METRICS | {"notes"}):
            errors.append(f"{prefix} metrics contain unknown property")
        if not REQUIRED_METRICS.issubset(metrics):
            errors.append(f"{prefix} metrics missing required property")
        for metric in (
            "synthetic_probability",
            "human_performance_probability",
            "confidence_score",
        ):
            value = metrics.get(metric)
            if value is not None and (
                not isinstance(value, (int, float)) or not 0 <= value <= 1
            ):
                errors.append(f"{prefix} invalid {metric}")
    return errors


def _recognized_missing_metric(instance: dict[str, Any]) -> bool:
    """Recognize the explicit missing-required-metric case as HOLD."""
    results = instance.get("analysis_results")
    return isinstance(results, list) and any(
        isinstance(result, dict)
        and isinstance(result.get("metrics"), dict)
        and not REQUIRED_METRICS.issubset(result["metrics"])
        for result in results
    )


def _test_only_conflict_policy(results: list[dict[str, Any]]) -> bool:
    """Test policy: probabilities on opposite sides of 0.5 conflict."""
    values = [
        result["metrics"]["synthetic_probability"]
        for result in results
        if isinstance(result, dict)
        and isinstance(result.get("metrics"), dict)
        and isinstance(
            result["metrics"].get("synthetic_probability"), (int, float)
        )
    ]
    return len(values) >= 2 and min(values) < 0.5 < max(values)


def evaluate_fixture_gate(
    instance: dict[str, Any],
    schema: dict[str, Any],
    actual_target_sha256: str,
) -> tuple[str, str | None]:
    """Reference gate for fixtures; digest must be computed independently."""
    # The contract allows recognized incomplete envelopes to HOLD before
    # final schema acceptance.
    if _recognized_missing_metric(instance):
        return "HOLD", "REQUIRED_METRIC_MISSING"

    if fixture_schema_errors(instance, schema):
        return "REFUSE", "SCHEMA_INVALID"

    digest = actual_target_sha256.lower()
    if instance["target_anchor"]["sha256"].lower() != digest:
        return "REFUSE", "TARGET_HASH_MISMATCH"
    if any(
        result["target_sha256"].lower() != digest
        for result in instance["analysis_results"]
    ):
        return "REFUSE", "TARGET_HASH_MISMATCH"

    if _test_only_conflict_policy(instance["analysis_results"]):
        return "INCONCLUSIVE", "ANALYZER_CONFLICT"
    return "VERIFIED", None


def test_av001_complete_audio_is_procedure_verified(
    vectors: dict[str, Any], schema: dict[str, Any]
) -> None:
    instance = copy.deepcopy(vectors["AV-001"]["input"])
    actual_digest = hashlib.sha256(b"AV-001 synthetic media bytes").hexdigest()
    instance["target_anchor"]["sha256"] = actual_digest
    for result in instance["analysis_results"]:
        result["target_sha256"] = actual_digest

    assert fixture_schema_errors(instance, schema) == []
    assert evaluate_fixture_gate(instance, schema, actual_digest) == ("VERIFIED", None)


def test_av002_target_hash_mismatch_refuses(
    vectors: dict[str, Any], schema: dict[str, Any]
) -> None:
    instance = vectors["AV-002"]["input"]
    actual_digest = hashlib.sha256(b"different actual media bytes").hexdigest()

    assert fixture_schema_errors(instance, schema) == []
    assert evaluate_fixture_gate(instance, schema, actual_digest) == (
        "REFUSE",
        "TARGET_HASH_MISMATCH",
    )


def test_av003_missing_required_metric_holds(
    vectors: dict[str, Any], schema: dict[str, Any]
) -> None:
    instance = vectors["AV-003"]["input"]
    actual_digest = instance["target_anchor"]["sha256"]

    errors = fixture_schema_errors(instance, schema)
    assert any("metrics missing required property" in error for error in errors)
    assert evaluate_fixture_gate(instance, schema, actual_digest) == (
        "HOLD",
        "REQUIRED_METRIC_MISSING",
    )


def test_av004_conflicting_analyzers_are_inconclusive(
    vectors: dict[str, Any], schema: dict[str, Any]
) -> None:
    instance = vectors["AV-004"]["input"]
    actual_digest = instance["target_anchor"]["sha256"]

    assert fixture_schema_errors(instance, schema) == []
    assert CONFLICT_POLICY_VERSION == "test-sign-disagreement-v1"
    assert evaluate_fixture_gate(instance, schema, actual_digest) == (
        "INCONCLUSIVE",
        "ANALYZER_CONFLICT",
    )
    # Preserve each analyzer output; do not average or select a winner.
    assert [
        result["metrics"]["synthetic_probability"]
        for result in instance["analysis_results"]
    ] == [0.93, 0.08]


def test_av005_unknown_top_level_field_refuses(
    vectors: dict[str, Any], schema: dict[str, Any]
) -> None:
    instance = vectors["AV-005"]["input"]
    actual_digest = instance["target_anchor"]["sha256"]

    assert "unknown top-level property" in fixture_schema_errors(instance, schema)
    assert evaluate_fixture_gate(instance, schema, actual_digest) == (
        "REFUSE",
        "SCHEMA_INVALID",
    )


def test_all_five_fixture_ids_and_expected_states_are_preserved(
    vectors: dict[str, Any],
) -> None:
    assert set(vectors) == {"AV-001", "AV-002", "AV-003", "AV-004", "AV-005"}
    assert {key: value["expected_state"] for key, value in vectors.items()} == {
        "AV-001": "VERIFIED",
        "AV-002": "REFUSE",
        "AV-003": "HOLD",
        "AV-004": "INCONCLUSIVE",
        "AV-005": "REFUSE",
    }
