"""Evidence-linked paired evaluator for The Hunt v0.3."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from api_ground_truth import api_valid_matrix, package_exists_matrix, validate_api_ground_truth
from provenance_checker import check_provenance
from signature_checker import check_signature
from temporal_contract import (
    check_signature_from_recovery,
    check_signature_from_snapshot,
    load_generation_snapshot,
)

POSITIVE_LABELS = {"HALLUCINATION", "HALLUCINATED_PACKAGE"}
NEGATIVE_LABELS = {"CLEAN", "NOT_HALLUCINATED"}
DEFINITIVE_PREDICTIONS = {"HALLUCINATION_CAUGHT", "CLEAN"}
BASELINE_HALLUCINATION = {"SYNTAX_ERROR", "PACKAGE_NOT_FOUND"}


def _api_boolean(signature: dict[str, Any]) -> bool | None:
    if signature.get("status") == "EXISTS":
        return True
    if signature.get("status") == "INVALID_SIGNATURE":
        return False
    return None


def _api_status(signature: dict[str, Any], axis: str) -> str:
    if signature.get("status") == "EXISTS":
        return f"VALID_{axis}"
    if signature.get("status") == "INVALID_SIGNATURE":
        return f"INVALID_{axis}"
    if signature.get("reason") == "TEMPORAL_EVIDENCE_MISSING":
        return "TEMPORAL_EVIDENCE_MISSING"
    return "INCONCLUSIVE"


def _ground_truth(value: Any) -> bool:
    if value is True or (isinstance(value, str) and value.upper() in POSITIVE_LABELS):
        return True
    if value is False or (isinstance(value, str) and value.upper() in NEGATIVE_LABELS):
        return False
    raise ValueError("ground_truth must be HALLUCINATION/CLEAN or a corresponding boolean")


def _jamp_verdict(provenance: dict[str, Any], signature: dict[str, Any]) -> str:
    if provenance.get("status") == "NOT_FOUND":
        return "HALLUCINATION_CAUGHT"
    if provenance.get("status") == "SUSPICIOUS":
        return "HALLUCINATION_CAUGHT"
    if signature.get("status") == "INVALID_SIGNATURE":
        return "HALLUCINATION_CAUGHT"
    if provenance.get("status") == "INCONCLUSIVE" or signature.get("status") == "INCONCLUSIVE":
        return "INCONCLUSIVE"
    if provenance.get("status") == "TRUSTED" and signature.get("status") == "EXISTS":
        return "CLEAN"
    return "INCONCLUSIVE"


def _baseline_verdict(code: str, package_exists: bool) -> str:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, TypeError):
        return "SYNTAX_ERROR"
    if not package_exists:
        return "PACKAGE_NOT_FOUND"
    has_import = any(
        isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)
    )
    if not has_import:
        return "NO_IMPORTS"
    return "CLEAN"


def _accuracy(
    rows: list[dict[str, Any]], prediction_key: str, *, baseline: bool = False
) -> dict[str, Any]:
    valid = DEFINITIVE_PREDICTIONS | BASELINE_HALLUCINATION
    scored = [row for row in rows if row[prediction_key] in valid]
    if not scored:
        return {"accuracy": None, "scored_count": 0, "correct_count": 0}
    correct = 0
    for row in scored:
        prediction = row[prediction_key]
        predicted_hallucination = (
            prediction in BASELINE_HALLUCINATION
            if baseline
            else prediction == "HALLUCINATION_CAUGHT"
        )
        correct += predicted_hallucination == row["actual_hallucination"]
    return {
        "accuracy": correct / len(scored),
        "scored_count": len(scored),
        "correct_count": correct,
    }


def exact_mcnemar(b: int, c: int) -> float:
    """Exact two-sided binomial McNemar p-value."""
    if b < 0 or c < 0:
        raise ValueError("discordant counts cannot be negative")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n)
    return float(min(1.0, 2.0 * tail))


def _read_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def evaluate(
    input_path: Path,
    output_path: Path,
    manifest_path: Path,
    ground_truth_path: Path,
    temporal_snapshot_path: Path | None = None,
    api_ground_truth_path: Path | None = None,
    prompts_path: Path | None = None,
    api_wheel_manifest_path: Path | None = None,
) -> dict[str, Any]:
    payload, raw_responses = _read_json(input_path)
    manifest, raw_manifest = _read_json(manifest_path)
    ground_truth_payload, raw_ground_truth = _read_json(ground_truth_path)

    if not isinstance(payload, dict) or not isinstance(payload.get("samples"), list):
        raise ValueError("LLM response input must contain a samples list")
    if not isinstance(manifest, dict):
        raise ValueError("generation manifest must be a JSON object")
    if not isinstance(ground_truth_payload, dict) or not isinstance(
        ground_truth_payload.get("samples"), list
    ):
        raise ValueError("ground truth must contain a samples list")

    response_hash = hashlib.sha256(raw_responses).hexdigest()
    manifest_hash = hashlib.sha256(raw_manifest).hexdigest()
    ground_truth_hash = hashlib.sha256(raw_ground_truth).hexdigest()
    if temporal_snapshot_path is None:
        candidate_snapshot = manifest_path.parent / "generation_snapshot.json"
        temporal_snapshot_path = candidate_snapshot if candidate_snapshot.is_file() else None
    temporal_snapshot = (
        load_generation_snapshot(temporal_snapshot_path)
        if temporal_snapshot_path is not None and temporal_snapshot_path.is_file()
        else None
    )
    if temporal_snapshot is not None:
        expected_snapshot_hash = manifest.get("generation_snapshot_sha256")
        if expected_snapshot_hash != temporal_snapshot.get("snapshot_sha256"):
            raise ValueError("generation snapshot SHA-256 does not match generation manifest")
    temporal_packages = (
        temporal_snapshot.get("_packages_by_sample", {})
        if temporal_snapshot is not None else {}
    )
    expected_response_hash = manifest.get("llm_responses_sha256")
    if expected_response_hash and expected_response_hash != response_hash:
        raise ValueError("LLM response file SHA-256 does not match generation manifest")
    expected_prompt_hash = manifest.get("prompt_dataset_sha256")
    if (
        not isinstance(expected_prompt_hash, str)
        or expected_prompt_hash != ground_truth_payload.get("prompt_dataset_sha256")
    ):
        raise ValueError("prompt dataset SHA-256 differs between manifest and ground truth")
    if manifest.get("provider_name") not in {"groq", "anymodel"}:
        raise ValueError("generation manifest provider_name must be groq or anymodel")
    if manifest.get("temperature") != 0.7:
        raise ValueError("generation manifest temperature must be exactly 0.7")
    if not isinstance(manifest.get("requested_model_id"), str) or not manifest[
        "requested_model_id"
    ].strip():
        raise ValueError("generation manifest requested_model_id is required")

    response_samples = payload["samples"]
    truth_samples = ground_truth_payload["samples"]
    if len(response_samples) != 100 or len(truth_samples) != 100:
        raise ValueError("v0.3 paired evaluation requires exactly 100 response and truth rows")
    if manifest.get("request_count") != 100:
        raise ValueError("generation manifest request_count must be exactly 100")
    if (
        manifest.get("successful_requests", 0)
        + manifest.get("abstained_requests", 0)
        + manifest.get("failed_requests", 0)
        != 100
    ):
        raise ValueError("generation manifest success/abstention/failure counts must total 100")

    ground_truth = {
        item.get("sample_id"): item
        for item in truth_samples
        if isinstance(item, dict) and isinstance(item.get("sample_id"), str)
    }
    if len(ground_truth) != 100:
        raise ValueError("ground-truth sample IDs must be 100 unique values")
    response_ids = [
        item.get("sample_id") for item in response_samples if isinstance(item, dict)
    ]
    successful_count = sum(
        item.get("request_status") == "SUCCESS" for item in response_samples
        if isinstance(item, dict)
    )
    abstained_count = sum(
        item.get("request_status") == "ABSTAINED" for item in response_samples
        if isinstance(item, dict)
    )
    if (
        manifest.get("successful_requests") != successful_count
        or manifest.get("abstained_requests", 0) != abstained_count
        or manifest.get("failed_requests")
        != len(response_samples) - successful_count - abstained_count
    ):
        raise ValueError("generation manifest request counts do not match response statuses")
    if len(response_ids) != 100 or len(set(response_ids)) != 100:
        raise ValueError("LLM response sample IDs must be 100 unique values")
    if set(response_ids) != set(ground_truth):
        raise ValueError("LLM response and ground-truth sample IDs do not match")

    results: list[dict[str, Any]] = []
    provenance_by_sample: dict[str, dict[str, Any]] = {}
    for index, sample in enumerate(response_samples):
        if not isinstance(sample, dict):
            raise ValueError(f"samples[{index}] must be an object")
        sample_id = sample.get("sample_id")
        truth = ground_truth[sample_id]
        label = truth.get("ground_truth")
        if label == "INCONCLUSIVE" or truth.get("pypi_exists") is None:
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": truth.get("package_name"),
                    "ground_truth": "INCONCLUSIVE",
                    "actual_hallucination": None,
                    "baseline_verdict": "INCONCLUSIVE",
                    "jamp_verdict": "INCONCLUSIVE",
                    "reason": "ground_truth_inconclusive",
                }
            )
            continue
        actual = _ground_truth(label)
        package_name = truth.get("package_name")
        if not isinstance(package_name, str) or not package_name.strip():
            raise ValueError(f"ground truth for {sample_id} lacks a valid package_name")
        provenance = check_provenance(package_name)
        provenance_by_sample[sample_id] = provenance
        request_status = sample.get("request_status")
        if request_status == "ABSTAINED":
            if (
                sample.get("package_name") != package_name
                or sample.get("prompt") != truth.get("prompt")
            ):
                results.append(
                    {
                        "sample_id": sample_id,
                        "package_name": package_name,
                        "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                        "actual_hallucination": actual,
                        "generation_status": "ABSTAINED",
                        "baseline_verdict": "INCONCLUSIVE",
                        "jamp_verdict": "INCONCLUSIVE",
                        "reason": "model_input_identity_mismatch",
                    }
                )
                continue
            code = sample.get("code")
            if not isinstance(code, str) or code.strip():
                raise ValueError("ABSTAINED response must contain an empty code string")
            package_exists = truth.get("pypi_exists")
            if not isinstance(package_exists, bool):
                raise ValueError(f"ground truth for {sample_id} lacks boolean pypi_exists")
            baseline = _baseline_verdict(code, package_exists)
            signature = {
                "status": "INCONCLUSIVE",
                "reason": "model_abstained_no_candidate_code",
            }
            verdict = _jamp_verdict(provenance, signature)
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": package_name,
                    "prompt": truth.get("prompt"),
                    "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                    "actual_hallucination": actual,
                    "generation_status": "ABSTAINED",
                    "baseline_verdict": baseline,
                    "jamp_verdict": verdict,
                    "provenance": provenance,
                    "signature": signature,
                    "reason": "model_abstained",
                }
            )
            continue
        if request_status != "SUCCESS":
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": truth.get("package_name"),
                    "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                    "actual_hallucination": actual,
                    "generation_status": request_status,
                    "baseline_verdict": "INCONCLUSIVE",
                    "jamp_verdict": "INCONCLUSIVE",
                    "reason": sample.get("failure_reason", "generation_not_successful"),
                }
            )
            continue

        if (
            sample.get("package_name") != package_name
            or sample.get("prompt") != truth.get("prompt")
        ):
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": package_name,
                    "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                    "actual_hallucination": actual,
                    "baseline_verdict": "INCONCLUSIVE",
                    "jamp_verdict": "INCONCLUSIVE",
                    "reason": "model_input_identity_mismatch",
                }
            )
            continue

        code = sample.get("code")
        if not isinstance(code, str) or not code.strip():
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": package_name,
                    "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                    "actual_hallucination": actual,
                    "baseline_verdict": "INCONCLUSIVE",
                    "jamp_verdict": "INCONCLUSIVE",
                    "reason": "missing_or_unparseable_generated_code",
                }
            )
            continue

        package_exists = truth.get("pypi_exists")
        if not isinstance(package_exists, bool):
            raise ValueError(f"ground truth for {sample_id} lacks boolean pypi_exists")
        baseline = _baseline_verdict(code, package_exists)
        signature_now = check_signature(code, package_name)
        temporal_record = temporal_packages.get(sample_id)
        signature_then = check_signature_from_snapshot(
            code, package_name, temporal_record, temporal_snapshot_path.parent
            if temporal_snapshot_path is not None else manifest_path.parent
        )
        signature = signature_then
        verdict = _jamp_verdict(provenance, signature_then)
        results.append(
            {
                "sample_id": sample_id,
                "package_name": package_name,
                "prompt": truth.get("prompt"),
                "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                "actual_hallucination": actual,
                "generation_status": "SUCCESS",
                "baseline_verdict": baseline,
                "jamp_verdict": verdict,
                "provenance": provenance,
                "signature": signature,
                "signature_now": signature_now,
                "signature_then": signature_then,
                "api_valid_now": _api_boolean(signature_now),
                "api_valid_then": _api_boolean(signature_then),
                "api_status_now": _api_status(signature_now, "NOW"),
                "api_status_then": _api_status(signature_then, "THEN"),
                "temporal_evidence_status": (
                    temporal_record.get("temporal_provenance", "UNRESOLVED")
                    if temporal_record else "TEMPORAL_EVIDENCE_MISSING"
                ),
            }
        )

    for row in results:
        sample_id = row.get("sample_id")
        if sample_id in provenance_by_sample:
            row.setdefault("provenance", provenance_by_sample[sample_id])
        temporal_record = temporal_packages.get(sample_id)
        row.setdefault("api_valid_now", None)
        row.setdefault("api_valid_then", None)
        row.setdefault("api_status_now", "INCONCLUSIVE")
        row.setdefault(
            "api_status_then",
            "TEMPORAL_EVIDENCE_MISSING" if temporal_record is None else "INCONCLUSIVE",
        )
        row.setdefault(
            "temporal_evidence_status",
            temporal_record.get("temporal_provenance", "UNRESOLVED")
            if temporal_record else "TEMPORAL_EVIDENCE_MISSING",
        )

    paired = [
        row
        for row in results
        if row["baseline_verdict"] in (DEFINITIVE_PREDICTIONS | BASELINE_HALLUCINATION)
        and row["jamp_verdict"] in DEFINITIVE_PREDICTIONS
        and row["actual_hallucination"] is not None
    ]
    jamp_only = sum(
        (row["jamp_verdict"] == "HALLUCINATION_CAUGHT") == row["actual_hallucination"]
        and (row["baseline_verdict"] in BASELINE_HALLUCINATION)
        != row["actual_hallucination"]
        for row in paired
    )
    baseline_only = sum(
        (row["baseline_verdict"] in BASELINE_HALLUCINATION)
        == row["actual_hallucination"]
        and (row["jamp_verdict"] == "HALLUCINATION_CAUGHT")
        != row["actual_hallucination"]
        for row in paired
    )
    abstained_results = [
        row for row in results if row.get("generation_status") == "ABSTAINED"
    ]
    api_status_now_values = {
        value
        for row in results
        if isinstance((value := row.get("api_status_now")), str)
    }
    api_status_then_values = {
        value
        for row in results
        if isinstance((value := row.get("api_status_then")), str)
    }
    temporal_evidence_status_values = {
        value
        for row in results
        if isinstance((value := row.get("temporal_evidence_status")), str)
    }
    report = {
        "schema_version": "jamp-hunt-evaluation-v0.3",
        "evidence_class": "LIVE_LLM_WITH_LIVE_PYPI_PACKAGE_EXISTENCE_LABELS",
        "qualification": "NOT_GRANTED",
        "generation_manifest_sha256": manifest_hash,
        "llm_responses_sha256": response_hash,
        "ground_truth_sha256": ground_truth_hash,
        "generation_snapshot_sha256": (
            temporal_snapshot.get("snapshot_sha256") if temporal_snapshot else None
        ),
        "api_valid_now_counts": {
            "valid": sum(row.get("api_valid_now") is True for row in results),
            "invalid": sum(row.get("api_valid_now") is False for row in results),
            "inconclusive": sum(row.get("api_valid_now") is None for row in results),
        },
        "api_valid_then_counts": {
            "valid": sum(row.get("api_valid_then") is True for row in results),
            "invalid": sum(row.get("api_valid_then") is False for row in results),
            "inconclusive": sum(row.get("api_valid_then") is None for row in results),
        },
        "api_status_now_counts": {
            status: sum(row.get("api_status_now") == status for row in results)
            for status in sorted(api_status_now_values)
        },
        "api_status_then_counts": {
            status: sum(row.get("api_status_then") == status for row in results)
            for status in sorted(api_status_then_values)
        },
        "temporal_evidence_status_counts": {
            status: sum(row.get("temporal_evidence_status") == status for row in results)
            for status in sorted(temporal_evidence_status_values)
        },
        "attempted_sample_count": len(results),
        "successful_generation_count": manifest.get("successful_requests"),
        "failed_generation_count": manifest.get("failed_requests"),
        "abstained_generation_count": manifest.get("abstained_requests", 0),
        "abstention_summary": {
            "count": len(abstained_results),
            "nonexistent_package_count": sum(
                row["actual_hallucination"] is True for row in abstained_results
            ),
            "existing_package_count": sum(
                row["actual_hallucination"] is False for row in abstained_results
            ),
        },
        "baseline": _accuracy(results, "baseline_verdict", baseline=True),
        "jamp": _accuracy(results, "jamp_verdict"),
        "inconclusive_count": sum(
            row["jamp_verdict"] == "INCONCLUSIVE" for row in results
        ),
        "ground_truth_inconclusive_count": sum(
            row["ground_truth"] == "INCONCLUSIVE" for row in results
        ),
        "paired_scored_count": len(paired),
        "mcnemar_exact_two_sided": {
            "jamp_correct_baseline_incorrect": jamp_only,
            "baseline_correct_jamp_incorrect": baseline_only,
            "discordant_pairs": jamp_only + baseline_only,
            "p_value": exact_mcnemar(jamp_only, baseline_only),
        },
        "results": results,
    }
    independent_inputs = (api_ground_truth_path, prompts_path, api_wheel_manifest_path)
    if any(path is not None for path in independent_inputs):
        if any(path is None for path in independent_inputs):
            raise ValueError(
                "API Ground Truth evaluation requires --api-ground-truth, --prompts, "
                "and --api-wheel-manifest together"
            )
        if temporal_snapshot is None:
            raise ValueError("API Ground Truth evaluation requires the verified temporal snapshot")
        api_payload, _ = _read_json(api_ground_truth_path)
        prompts_payload, _ = _read_json(prompts_path)
        wheel_manifest_payload, _ = _read_json(api_wheel_manifest_path)
        if not all(
            isinstance(value, dict)
            for value in (api_payload, prompts_payload, wheel_manifest_payload)
        ):
            raise ValueError("API Ground Truth, prompts, and wheel manifest must be JSON objects")
        api_rows = validate_api_ground_truth(
            api_payload, payload, ground_truth_payload, prompts_payload,
            temporal_snapshot, wheel_manifest_payload
        )
        response_by_sample = {
            item["sample_id"]: item for item in response_samples
            if isinstance(item, dict) and isinstance(item.get("sample_id"), str)
        }
        result_by_sample = {item["sample_id"]: item for item in results}
        for sample_id, api_row in api_rows.items():
            if api_row.get("api_status") not in {"VALID", "INVALID"}:
                continue
            response_row = response_by_sample[sample_id]
            result_row = result_by_sample[sample_id]
            result_row["signature_api_gt"] = check_signature_from_recovery(
                response_row.get("code", ""),
                api_row["package_name"],
                temporal_packages.get(sample_id),
                api_row["provenance"]["recovery_wheels"],
                api_wheel_manifest_path.parent,
                sample_id,
            )
        report["matrix_package_exists"] = package_exists_matrix(results, truth_samples)
        report["matrix_api_valid"] = api_valid_matrix(api_rows, results)
        report["independent_api_ground_truth"] = {
            "checker_basis": "HASH_VERIFIED_RECOVERY_WHEEL_AT_SNAPSHOT_PINNED_VERSION",
            "temporal_limitation": (
                "Checker inspected a hash-verified recovery-time compatible wheel whose direct "
                "package version exactly matches the generation snapshot. This does not prove "
                "the original generation-time wheel build or transitive dependency closure."
            ),
            "schema_version": api_payload["schema_version"],
            "sample_count": len(api_rows),
            "api_ground_truth_counts": api_payload["api_ground_truth_counts"],
            "qualification": "NOT_GRANTED",
            "validity_scope": api_payload["api_validity_scope"],
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("llm_responses_v3.json"))
    parser.add_argument("--manifest", type=Path, default=Path("generation_manifest.json"))
    parser.add_argument("--ground-truth", type=Path, default=Path("ground_truth_v3.json"))
    parser.add_argument("--output", type=Path, default=Path("results_v0.3.json"))
    parser.add_argument("--temporal-snapshot", type=Path)
    parser.add_argument("--api-ground-truth", type=Path)
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--api-wheel-manifest", type=Path)
    args = parser.parse_args()
    report = evaluate(
        args.input, args.output, args.manifest, args.ground_truth,
        args.temporal_snapshot, args.api_ground_truth, args.prompts,
        args.api_wheel_manifest
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "attempted_sample_count": report["attempted_sample_count"],
                "paired_scored_count": report["paired_scored_count"],
                "inconclusive_count": report["inconclusive_count"],
                "qualification": report["qualification"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
