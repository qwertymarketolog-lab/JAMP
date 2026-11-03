"""Evidence-linked paired evaluator for The Hunt v0.3."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from provenance_checker import check_provenance
from signature_checker import check_signature

POSITIVE_LABELS = {"HALLUCINATION", "HALLUCINATED_PACKAGE"}
NEGATIVE_LABELS = {"CLEAN", "NOT_HALLUCINATED"}
DEFINITIVE_PREDICTIONS = {"HALLUCINATION_CAUGHT", "CLEAN"}
BASELINE_HALLUCINATION = {"SYNTAX_ERROR", "PACKAGE_NOT_FOUND"}


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
    return min(1.0, 2.0 * tail)


def _read_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def evaluate(
    input_path: Path,
    output_path: Path,
    manifest_path: Path,
    ground_truth_path: Path,
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
        or manifest.get("failed_requests") != len(response_samples) - successful_count - abstained_count
    ):
        raise ValueError("generation manifest request counts do not match response statuses")
    if len(response_ids) != 100 or len(set(response_ids)) != 100:
        raise ValueError("LLM response sample IDs must be 100 unique values")
    if set(response_ids) != set(ground_truth):
        raise ValueError("LLM response and ground-truth sample IDs do not match")

    results: list[dict[str, Any]] = []
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
        request_status = sample.get("request_status")
        if request_status == "ABSTAINED":
            package_name = truth.get("package_name")
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
            provenance = check_provenance(package_name)
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

        package_name = truth.get("package_name")
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
        provenance = check_provenance(package_name)
        signature = check_signature(code, package_name)
        verdict = _jamp_verdict(provenance, signature)
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
            }
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
    report = {
        "schema_version": "jamp-hunt-evaluation-v0.3",
        "evidence_class": "LIVE_LLM_WITH_LIVE_PYPI_PACKAGE_EXISTENCE_LABELS",
        "qualification": "NOT_GRANTED",
        "generation_manifest_sha256": manifest_hash,
        "llm_responses_sha256": response_hash,
        "ground_truth_sha256": ground_truth_hash,
        "attempted_sample_count": len(results),
        "successful_generation_count": manifest.get("successful_requests"),
        "failed_generation_count": manifest.get("failed_requests"),
        "abstained_generation_count": manifest.get("abstained_requests"),
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
    args = parser.parse_args()
    report = evaluate(args.input, args.output, args.manifest, args.ground_truth)
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
