"""Replay pinned synthetic API examples through JAMP's static signature checker."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from signature_checker import _imports_and_calls, inspect_wheel_bytes  # noqa: E402

RECOVERY_ARTIFACT_ID = 13299716958
RECOVERY_ARTIFACT_SHA256 = "93cf36e696897bfca8ab99e500a8e625e8bae131d5944f56b1cb879ccdeae3b6"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_member(source: Path, member: str) -> bytes:
    if source.is_dir():
        return (source / member).read_bytes()
    with zipfile.ZipFile(source) as archive:
        return archive.read(member)


def evaluate(cohort_path: Path, recovery_path: Path, output_path: Path) -> dict[str, Any]:
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    recovery_digest = (
        sha256(recovery_path.read_bytes()) if recovery_path.is_file() else None
    )
    if recovery_digest is not None and recovery_digest != RECOVERY_ARTIFACT_SHA256:
        raise ValueError("Recovery artifact ZIP SHA-256 mismatch")
    if cohort.get("recovery_artifact_id") != RECOVERY_ARTIFACT_ID:
        raise ValueError("unexpected Recovery artifact ID")

    manifest_raw = read_member(recovery_path, "recovery-input/wheel_manifest.json")
    if sha256(manifest_raw) != cohort.get("wheel_manifest_sha256"):
        raise ValueError("wheel manifest digest differs from cohort")
    manifest = json.loads(manifest_raw)
    wheel_index = {item["filename"]: item for item in manifest["wheels"]}
    rows: list[dict[str, Any]] = []

    for axis, key in (
        ("NEGATIVE", "negative_samples"),
        ("POSITIVE_CONTROL", "positive_controls"),
    ):
        for sample in cohort[key]:
            evidence = sample["ground_truth_evidence"]
            filename = evidence["wheel_filename"]
            wheel = wheel_index.get(filename)
            if wheel is None or wheel["sha256"] != evidence["wheel_sha256"]:
                raise ValueError(f"wheel manifest mismatch: {sample['sample_id']}")
            wheel_bytes = read_member(
                recovery_path, f"recovery-input/wheelhouse/{filename}"
            )
            if sha256(wheel_bytes) != evidence["wheel_sha256"]:
                raise ValueError(f"wheel bytes digest mismatch: {sample['sample_id']}")
            aliases, calls, unsupported = _imports_and_calls(
                sample["code_snippet"], sample["package_name"]
            )
            result = (
                inspect_wheel_bytes(wheel_bytes, calls, unsupported)
                if aliases
                else {"status": "INCONCLUSIVE", "reason": "package_import_not_found"}
            )
            actual = result["status"]
            if axis == "NEGATIVE":
                classification = (
                    "TRUE_POSITIVE" if actual == "INVALID_SIGNATURE"
                    else "FALSE_NEGATIVE" if actual == "EXISTS"
                    else "INCONCLUSIVE"
                )
            else:
                classification = (
                    "FALSE_POSITIVE" if actual == "INVALID_SIGNATURE"
                    else "TRUE_NEGATIVE" if actual == "EXISTS"
                    else "INCONCLUSIVE"
                )
            rows.append({
                "sample_id": sample["sample_id"],
                "axis": axis,
                "package_name": sample["package_name"],
                "ground_truth": sample["ground_truth"],
                "checker_status": actual,
                "classification": classification,
                "checker_evidence": result,
                "wheel_filename": filename,
                "wheel_sha256": evidence["wheel_sha256"],
            })

    negative = [row for row in rows if row["axis"] == "NEGATIVE"]
    positive = [row for row in rows if row["axis"] == "POSITIVE_CONTROL"]
    neg_counts = Counter(row["classification"] for row in negative)
    pos_counts = Counter(row["classification"] for row in positive)
    report = {
        "schema_version": "jamp-hunt-api-negative-results-v0.1",
        "evaluation_mode": "PINNED_WHEEL_STATIC_SYNTHETIC_NEGATIVE",
        "recovery_artifact_id": RECOVERY_ARTIFACT_ID,
        "recovery_artifact_sha256": recovery_digest or RECOVERY_ARTIFACT_SHA256,
        "wheel_manifest_sha256": cohort["wheel_manifest_sha256"],
        "package_count": cohort["package_count"],
        "negative_sample_count": len(negative),
        "positive_control_count": len(positive),
        "true_positives": neg_counts["TRUE_POSITIVE"],
        "false_negatives": neg_counts["FALSE_NEGATIVE"] + neg_counts["INCONCLUSIVE"],
        "strict_false_negatives_exists": neg_counts["FALSE_NEGATIVE"],
        "negative_inconclusive": neg_counts["INCONCLUSIVE"],
        "false_positives": pos_counts["FALSE_POSITIVE"],
        "true_negatives": pos_counts["TRUE_NEGATIVE"],
        "positive_inconclusive": pos_counts["INCONCLUSIVE"],
        "false_positives_measured_on_positive_controls": True,
        "false_positives_on_negative_only_cohort": "NOT_APPLICABLE",
        "generated_model_code_executed": False,
        "qualification": "NOT_GRANTED",
        "results": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--recovery-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.cohort, args.recovery_artifact, args.output)
    fields = (
        "evaluation_mode", "negative_sample_count", "true_positives",
        "false_negatives", "strict_false_negatives_exists", "negative_inconclusive",
        "positive_control_count", "false_positives", "true_negatives",
        "positive_inconclusive", "qualification",
    )
    print(json.dumps({key: report[key] for key in fields}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
