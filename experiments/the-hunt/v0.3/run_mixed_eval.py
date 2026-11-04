"""Evaluate original Nemotron outputs against Recovery-time API Ground Truth.

This is explicitly MIXED_TEMPORAL: LLM outputs are from the original generation
run, while API observations and wheel bytes are from the later recovery run.
Candidate code is parsed only; it is never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from signature_checker import _imports_and_calls, inspect_wheel_bytes  # noqa: E402

SOURCE_ARTIFACT_ID = 13257610773
RECOVERY_ARTIFACT_ID = 13299716958
SOURCE_ARTIFACT_SHA256 = (
    "9e0ff74b4f3450044224fc457ef9dae8f831c77773852dc9bf985a846be7c5a3"
)
RECOVERY_ARTIFACT_SHA256 = (
    "93cf36e696897bfca8ab99e500a8e625e8bae131d5944f56b1cb879ccdeae3b6"
)
RECOVERY_RUN_ID = 41782136773


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _member(archive: zipfile.ZipFile, suffix: str) -> str:
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one ZIP member ending in {suffix!r}")
    return matches[0]


def _json_member(archive: zipfile.ZipFile, suffix: str) -> tuple[Any, bytes]:
    raw = archive.read(_member(archive, suffix))
    return json.loads(raw.decode("utf-8")), raw


def _normalise_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _wheel_index(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    wheels = manifest.get("wheels")
    if not isinstance(wheels, list):
        raise ValueError("wheel manifest must contain a wheels list")
    index: dict[str, dict[str, Any]] = {}
    for wheel in wheels:
        if not isinstance(wheel, dict):
            raise ValueError("wheel manifest entry must be an object")
        filename = wheel.get("filename")
        digest = wheel.get("sha256")
        if not isinstance(filename, str) or not isinstance(digest, str):
            raise ValueError("wheel manifest entry lacks filename or sha256")
        distribution = filename.split("-", 1)[0]
        key = _normalise_distribution(distribution)
        if key in index:
            raise ValueError(f"duplicate normalized wheel distribution: {key}")
        index[key] = wheel
    return index


def _verify_recovery_wheels(
    archive: zipfile.ZipFile, manifest: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    index = _wheel_index(manifest)
    for wheel in index.values():
        filename = wheel["filename"]
        member = f"recovery-input/wheelhouse/{filename}"
        if member not in archive.namelist():
            raise ValueError(f"recovery wheel is missing: {filename}")
        observed = _sha256(archive.read(member))
        if observed != wheel["sha256"]:
            raise ValueError(f"recovery wheel SHA-256 mismatch: {filename}")
    return index


def _classify(api_status: str, signature_status: str) -> str:
    if api_status == "VALID" and signature_status == "INVALID_SIGNATURE":
        return "FALSE_POSITIVE"
    if api_status == "INVALID" and signature_status == "INVALID_SIGNATURE":
        return "TRUE_POSITIVE"
    if api_status == "VALID" and signature_status == "EXISTS":
        return "TRUE_NEGATIVE"
    if api_status == "INVALID" and signature_status == "EXISTS":
        return "FALSE_NEGATIVE"
    return "INCONCLUSIVE"


def evaluate(
    source_zip: Path,
    recovery_zip: Path,
    output_path: Path,
) -> dict[str, Any]:
    source_bytes = source_zip.read_bytes()
    recovery_bytes = recovery_zip.read_bytes()
    source_digest = _sha256(source_bytes)
    recovery_digest = _sha256(recovery_bytes)
    if source_digest != SOURCE_ARTIFACT_SHA256:
        raise ValueError("original source artifact SHA-256 does not match pinned ID")
    if recovery_digest != RECOVERY_ARTIFACT_SHA256:
        raise ValueError("recovery artifact SHA-256 does not match pinned run")

    with zipfile.ZipFile(source_zip) as source, zipfile.ZipFile(recovery_zip) as recovery:
        manifest, manifest_raw = _json_member(source, "generation_manifest.json")
        responses, responses_raw = _json_member(source, "llm_responses_v3.json")
        ground_truth, ground_truth_raw = _json_member(source, "ground_truth_v3.json")
        api_gt, _ = _json_member(recovery, "api_ground_truth_v0.3.json")
        recovery_results, _ = _json_member(recovery, "results_v0.3.json")
        wheel_manifest, wheel_manifest_raw = _json_member(
            recovery, "recovery-input/wheel_manifest.json"
        )

        if manifest.get("llm_responses_sha256") != _sha256(responses_raw):
            raise ValueError("original response SHA-256 differs from manifest")
        if manifest.get("prompt_dataset_sha256") != ground_truth.get(
            "prompt_dataset_sha256"
        ):
            raise ValueError("original prompt dataset digest mismatch")
        if recovery_results.get("source_artifact_id") != SOURCE_ARTIFACT_ID:
            raise ValueError("recovery results reference a different source artifact")
        if recovery_results.get("source_artifact_sha256") != source_digest:
            raise ValueError("recovery results source artifact digest mismatch")
        if recovery_results.get("source_manifest_sha256") != _sha256(manifest_raw):
            raise ValueError("recovery results source manifest digest mismatch")
        if recovery_results.get("source_responses_sha256") != _sha256(responses_raw):
            raise ValueError("recovery results source response digest mismatch")
        if recovery_results.get("source_ground_truth_sha256") != _sha256(
            ground_truth_raw
        ):
            raise ValueError("recovery results source Ground Truth digest mismatch")
        if api_gt.get("source_artifact_id") != SOURCE_ARTIFACT_ID:
            raise ValueError("API Ground Truth references a different source artifact")
        wheel_manifest_digest = _sha256(wheel_manifest_raw)
        if api_gt.get("wheel_manifest_sha256") != wheel_manifest_digest:
            raise ValueError("API Ground Truth wheel manifest digest mismatch")
        if recovery_results.get("wheel_manifest_sha256") != wheel_manifest_digest:
            raise ValueError("recovery results wheel manifest digest mismatch")

        wheel_index = _verify_recovery_wheels(recovery, wheel_manifest)
        response_rows = responses.get("samples")
        truth_rows = ground_truth.get("samples")
        api_rows = api_gt.get("samples")
        if not all(isinstance(rows, list) for rows in (response_rows, truth_rows, api_rows)):
            raise ValueError("source and API Ground Truth samples must be lists")
        if not (len(response_rows) == len(truth_rows) == len(api_rows) == 100):
            raise ValueError("MIXED_TEMPORAL evaluation requires aligned 100-row inputs")

        truth_by_id = {row["sample_id"]: row for row in truth_rows}
        api_by_id = {row["sample_id"]: row for row in api_rows}
        if len(truth_by_id) != 100 or len(api_by_id) != 100:
            raise ValueError("sample IDs must be unique in both Ground Truth datasets")
        if set(truth_by_id) != set(api_by_id):
            raise ValueError("recovery API Ground Truth sample IDs do not align")

        results: list[dict[str, Any]] = []
        for sample in response_rows:
            sample_id = sample.get("sample_id")
            truth = truth_by_id.get(sample_id)
            api = api_by_id.get(sample_id)
            if truth is None or api is None:
                raise ValueError(f"unmatched sample ID: {sample_id}")
            package_name = truth.get("package_name")
            if (
                sample.get("package_name") != package_name
                or api.get("package_name") != package_name
            ):
                raise ValueError(f"package identity mismatch for {sample_id}")

            request_status = sample.get("request_status")
            if request_status != "SUCCESS":
                results.append(
                    {
                        "sample_id": sample_id,
                        "package_name": package_name,
                        "generation_status": request_status,
                        "api_ground_truth_status": api.get("api_status"),
                        "signature_status": "INCONCLUSIVE",
                        "classification": "INCONCLUSIVE",
                        "reason": "original_generation_not_successful",
                    }
                )
                continue

            code = sample.get("code")
            if not isinstance(code, str) or not code.strip():
                signature = {
                    "status": "INCONCLUSIVE",
                    "reason": "successful_response_missing_code",
                }
            else:
                wheel = wheel_index.get(_normalise_distribution(package_name))
                if wheel is None:
                    signature = {
                        "status": "INCONCLUSIVE",
                        "reason": "recovery_wheel_not_found",
                    }
                else:
                    aliases, calls, unsupported = _imports_and_calls(
                        code, package_name
                    )
                    if not aliases:
                        signature = {
                            "status": "INCONCLUSIVE",
                            "reason": "package_import_not_found",
                        }
                    else:
                        wheel_path = (
                            f"recovery-input/wheelhouse/{wheel['filename']}"
                        )
                        signature = inspect_wheel_bytes(
                            recovery.read(wheel_path), calls, unsupported
                        )
                        signature.update(
                            {
                                "wheel_filename": wheel["filename"],
                                "wheel_sha256": wheel["sha256"],
                                "import_aliases": sorted(aliases),
                            }
                        )

            api_status = api.get("api_status")
            if api_status not in {"VALID", "INVALID", "INCONCLUSIVE"}:
                api_status = "INCONCLUSIVE"
            signature_status = signature.get("status")
            classification = _classify(
                api_status,
                signature_status if isinstance(signature_status, str) else "INCONCLUSIVE",
            )
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": package_name,
                    "generation_status": request_status,
                    "api_ground_truth_status": api_status,
                    "api_ground_truth_valid": api.get("api_valid"),
                    "signature_status": signature_status,
                    "signature": signature,
                    "classification": classification,
                }
            )

    class_counts = Counter(row["classification"] for row in results)
    api_counts = Counter(row["api_ground_truth_status"] for row in results)
    invalid_api_count = api_counts["INVALID"]
    report = {
        "schema_version": "jamp-hunt-mixed-temporal-v0.1",
        "evaluation_mode": "MIXED_TEMPORAL",
        "temporal_contract": "THEN_LLM_GENERATION_PLUS_RECOVERY_NOW_API_GROUND_TRUTH",
        "source_artifact_id": SOURCE_ARTIFACT_ID,
        "source_artifact_sha256": source_digest,
        "source_generation_timestamp_utc": manifest.get("generation_timestamp_utc"),
        "source_provider": manifest.get("provider_name"),
        "source_model_id": manifest.get("provider_model_id"),
        "recovery_artifact_id": RECOVERY_ARTIFACT_ID,
        "recovery_run_id": RECOVERY_RUN_ID,
        "recovery_artifact_sha256": recovery_digest,
        "api_ground_truth_method": api_gt.get("method"),
        "api_ground_truth_scope": api_gt.get("api_validity_scope"),
        "api_ground_truth_runtime_note": api_gt.get("runtime_snapshot_note"),
        "wheel_manifest_sha256": wheel_manifest_digest,
        "wheel_count": wheel_manifest.get("wheel_count"),
        "generated_model_code_executed": False,
        "api_ground_truth_counts": dict(sorted(api_counts.items())),
        "false_positives": class_counts["FALSE_POSITIVE"],
        "true_positives": class_counts["TRUE_POSITIVE"],
        "true_positive_evaluation_possible": invalid_api_count > 0,
        "true_positive_ground_truth_denominator": invalid_api_count,
        "true_negatives": class_counts["TRUE_NEGATIVE"],
        "false_negatives": class_counts["FALSE_NEGATIVE"],
        "inconclusive": class_counts["INCONCLUSIVE"],
        "qualification": "NOT_GRANTED",
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
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--recovery-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.source_artifact, args.recovery_artifact, args.output)
    print(
        json.dumps(
            {
                "evaluation_mode": report["evaluation_mode"],
                "false_positives": report["false_positives"],
                "true_positives": report["true_positives"],
                "true_positive_evaluation_possible": report[
                    "true_positive_evaluation_possible"
                ],
                "inconclusive": report["inconclusive"],
                "qualification": report["qualification"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
