"""Independent package-existence and API-validity matrices for The Hunt v0.3."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

SOURCE_ARTIFACT_ID = 13347295508
SOURCE_ARTIFACT_SHA256 = "576c570f0d960719ccf68f16a632f373352e066e3c12f0474978659ebeeb08b5"
API_GT_SCHEMA = "jamp-hunt-api-ground-truth-v0.3"
WHEEL_MANIFEST_SCHEMA = "jamp.hunt.recovery-wheelhouse.v2"
API_METHOD = "AST_STATIC_IMPORT_ATTRIBUTE_CALLABILITY_RUNTIME_PROBE"


def _canonical_row_sha256(row: dict[str, Any]) -> str:
    raw = json.dumps(
        row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _unique_index(rows: Any, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError(f"{label} must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sample_id"), str):
            raise ValueError(f"{label} rows require sample_id")
        sample_id = row["sample_id"]
        if sample_id in indexed:
            raise ValueError(f"{label} contains duplicate sample_id: {sample_id}")
        indexed[sample_id] = row
    return indexed


def validate_api_ground_truth(
    api_payload: dict[str, Any],
    responses_payload: dict[str, Any],
    package_gt_payload: dict[str, Any],
    prompts_payload: dict[str, Any],
    temporal_snapshot: dict[str, Any],
    wheel_manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Validate independent API GT against every original and recovery provenance edge."""
    if api_payload.get("schema_version") != API_GT_SCHEMA:
        raise ValueError("unsupported independent API Ground Truth schema")
    if api_payload.get("qualification") != "NOT_GRANTED":
        raise ValueError("API Ground Truth qualification must remain NOT_GRANTED")
    if "not signatures or behavior" not in str(api_payload.get("api_validity_scope", "")):
        raise ValueError("API Ground Truth scope must explicitly exclude signatures and behavior")
    if (
        api_payload.get("source_artifact_id") != SOURCE_ARTIFACT_ID
        or api_payload.get("source_artifact_sha256") != SOURCE_ARTIFACT_SHA256
    ):
        raise ValueError("API Ground Truth source artifact identity mismatch")
    snapshot_sha = temporal_snapshot.get("snapshot_sha256")
    if not isinstance(snapshot_sha, str) or api_payload.get("snapshot_sha256") != snapshot_sha:
        raise ValueError("API Ground Truth generation snapshot identity mismatch")
    if wheel_manifest.get("schema_version") != WHEEL_MANIFEST_SCHEMA:
        raise ValueError("unsupported recovery wheel manifest schema")
    wheel_bytes = (
        json.dumps(wheel_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    wheel_sha = hashlib.sha256(wheel_bytes).hexdigest()
    if api_payload.get("wheel_manifest_sha256") != wheel_sha:
        raise ValueError("API Ground Truth recovery wheel manifest SHA-256 mismatch")

    response_rows = _unique_index(responses_payload.get("samples"), "LLM responses")
    package_rows = _unique_index(package_gt_payload.get("samples"), "Package Ground Truth")
    prompt_rows = _unique_index(prompts_payload.get("samples"), "original prompts")
    api_rows = _unique_index(api_payload.get("samples"), "API Ground Truth")
    snapshot_rows = temporal_snapshot.get("_packages_by_sample")
    if not isinstance(snapshot_rows, dict):
        snapshot_rows = {
            row["sample_id"]: row
            for row in temporal_snapshot.get("packages", [])
            if isinstance(row, dict) and isinstance(row.get("sample_id"), str)
        }
    wheel_rows = wheel_manifest.get("wheels")
    if not isinstance(wheel_rows, list):
        raise ValueError("recovery wheel manifest wheels must be a list")
    wheel_rows_by_sample: dict[str, list[dict[str, Any]]] = {}
    for wheel in wheel_rows:
        if not isinstance(wheel, dict) or not isinstance(wheel.get("sample_id"), str):
            raise ValueError("recovery wheel manifest contains an invalid wheel row")
        wheel_rows_by_sample.setdefault(wheel["sample_id"], []).append(wheel)

    expected_ids = set(response_rows)
    if (
        len(expected_ids) != 100
        or set(package_rows) != expected_ids
        or set(prompt_rows) != expected_ids
        or set(api_rows) != expected_ids
        or set(snapshot_rows) != expected_ids
    ):
        raise ValueError("API Ground Truth provenance requires exact 100-row sample alignment")

    counts: Counter[str] = Counter()
    for sample_id, api_row in api_rows.items():
        status = api_row.get("api_status")
        if status not in {"VALID", "INVALID", "INCONCLUSIVE"}:
            raise ValueError(f"{sample_id}: invalid api_status")
        expected_valid = {"VALID": True, "INVALID": False, "INCONCLUSIVE": None}[status]
        if api_row.get("api_valid") is not expected_valid:
            raise ValueError(f"{sample_id}: api_valid conflicts with api_status")
        counts[status] += 1

        response = response_rows[sample_id]
        package_gt = package_rows[sample_id]
        prompt = prompt_rows[sample_id]
        provenance = api_row.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError(f"{sample_id}: API GT provenance is missing")
        if (
            api_row.get("package_name") != response.get("package_name")
            or api_row.get("package_name") != package_gt.get("package_name")
            or api_row.get("package_name") != prompt.get("package_name")
        ):
            raise ValueError(f"{sample_id}: package identity mismatch")
        if (
            api_row.get("package_exists") is not package_gt.get("pypi_exists")
            or api_row.get("generation_status") != response.get("request_status")
            or provenance.get("original_package_gt") != package_gt.get("ground_truth")
        ):
            raise ValueError(f"{sample_id}: original Package GT or generation status mismatch")
        if provenance.get("response_row_sha256") != _canonical_row_sha256(response):
            raise ValueError(f"{sample_id}: original response row hash mismatch")
        if provenance.get("prompt_row_sha256") != _canonical_row_sha256(prompt):
            raise ValueError(f"{sample_id}: original prompt row hash mismatch")
        if (
            provenance.get("source_artifact_id") != SOURCE_ARTIFACT_ID
            or provenance.get("source_artifact_sha256") != SOURCE_ARTIFACT_SHA256
            or provenance.get("snapshot_sha256") != snapshot_sha
            or provenance.get("recovery_wheel_manifest_sha256") != wheel_sha
        ):
            raise ValueError(f"{sample_id}: per-sample source provenance mismatch")
        if provenance.get("snapshot_package_record") != snapshot_rows[sample_id]:
            raise ValueError(f"{sample_id}: generation snapshot record mismatch")
        if provenance.get("recovery_wheels") != wheel_rows_by_sample.get(sample_id, []):
            raise ValueError(f"{sample_id}: recovery wheel provenance mismatch")
        if (
            provenance.get("response_file") != "llm_responses_v3.json"
            or provenance.get("prompt_file") != "prompts.json"
            or provenance.get("ground_truth_file") != "ground_truth_v3.json"
            or provenance.get("snapshot_file") != "generation_snapshot.json"
            or provenance.get("api_method") != API_METHOD
        ):
            raise ValueError(f"{sample_id}: source file or probe method provenance mismatch")
        excluded = provenance.get("api_scope_excludes")
        if not isinstance(excluded, list) or not {
            "function_signatures", "behavioral_compatibility"
        }.issubset(set(excluded)):
            raise ValueError(f"{sample_id}: API GT scope exclusion evidence is missing")

    if dict(counts) != api_payload.get("api_ground_truth_counts"):
        raise ValueError("API Ground Truth declared counts do not match sample rows")
    return api_rows


def package_exists_matrix(
    results: list[dict[str, Any]],
    package_gt_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score package existence using only original Package GT and provenance status."""
    package_gt = _unique_index(package_gt_rows, "Package Ground Truth")
    counts = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    inconclusive = 0
    for result in results:
        sample_id = result.get("sample_id")
        truth = package_gt.get(sample_id) if isinstance(sample_id, str) else None
        if truth is None or not isinstance(truth.get("pypi_exists"), bool):
            inconclusive += 1
            continue
        provenance = result.get("provenance")
        status = provenance.get("status") if isinstance(provenance, dict) else None
        predicted = (
            True if status in {"TRUSTED", "SUSPICIOUS"}
            else False if status == "NOT_FOUND"
            else None
        )
        if predicted is None:
            inconclusive += 1
            continue
        actual = truth["pypi_exists"]
        if actual and predicted:
            counts["TP"] += 1
        elif not actual and not predicted:
            counts["TN"] += 1
        elif not actual and predicted:
            counts["FP"] += 1
        else:
            counts["FN"] += 1
    return {
        "positive_class": "EXISTS",
        **counts,
        "scored_count": sum(counts.values()),
        "inconclusive_count": inconclusive,
    }


def api_valid_matrix(
    api_rows: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score invalid-API detection; INCONCLUSIVE rows never become negatives."""
    result_rows = _unique_index(results, "Evaluator results")
    counts = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    gt_excluded = 0
    checker_inconclusive = 0
    for sample_id, truth in api_rows.items():
        gt_status = truth["api_status"]
        if gt_status == "INCONCLUSIVE":
            gt_excluded += 1
            continue
        result = result_rows.get(sample_id)
        signature = result.get("signature_api_gt") if result else None
        checker_status = signature.get("status") if isinstance(signature, dict) else None
        if checker_status not in {"EXISTS", "INVALID_SIGNATURE"}:
            checker_inconclusive += 1
            continue
        actual_invalid = gt_status == "INVALID"
        predicted_invalid = checker_status == "INVALID_SIGNATURE"
        if actual_invalid and predicted_invalid:
            counts["TP"] += 1
        elif not actual_invalid and not predicted_invalid:
            counts["TN"] += 1
        elif not actual_invalid and predicted_invalid:
            counts["FP"] += 1
        else:
            counts["FN"] += 1
    return {
        "positive_class": "INVALID",
        "checker_basis": "HASH_VERIFIED_RECOVERY_WHEEL_AT_SNAPSHOT_PINNED_VERSION",
        "temporal_scope": (
            "Recovery-time compatible wheel at the exact snapshot-pinned direct version; "
            "does not establish the original generation-time wheel build "
            "or transitive dependency closure."
        ),
        **counts,
        "scored_count": sum(counts.values()),
        "api_gt_inconclusive_excluded": gt_excluded,
        "checker_inconclusive": checker_inconclusive,
    }
