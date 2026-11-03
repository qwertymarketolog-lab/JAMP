"""Paired evaluator for The Hunt v0.3.

Input is real or otherwise explicitly labelled generated data. This script does
not generate LLM responses and never installs or executes candidate packages.
"""
from __future__ import annotations

import argparse
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


def _ground_truth(value: Any) -> bool:
    if value is True or (isinstance(value, str) and value.upper() in POSITIVE_LABELS):
        return True
    if value is False or (isinstance(value, str) and value.upper() in NEGATIVE_LABELS):
        return False
    raise ValueError(
        "ground_truth must be HALLUCINATION/CLEAN or a corresponding boolean"
    )


def _jamp_verdict(provenance: dict[str, Any], signature: dict[str, Any]) -> str:
    # A confirmed PyPI 404 is definitive even though no wheel can be inspected.
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


def _accuracy(rows: list[dict[str, Any]], prediction_key: str) -> dict[str, Any]:
    scored = [
        row for row in rows
        if row[prediction_key] in DEFINITIVE_PREDICTIONS
    ]
    if not scored:
        return {"accuracy": None, "scored_count": 0, "correct_count": 0}
    correct = sum(
        (row[prediction_key] == "HALLUCINATION_CAUGHT") == row["actual_hallucination"]
        for row in scored
    )
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


def evaluate(input_path: Path, output_path: Path) -> dict[str, Any]:
    raw_input = input_path.read_bytes()
    payload = json.loads(raw_input.decode("utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else payload
    if not isinstance(samples, list):
        raise ValueError("input JSON must be a list or an object containing samples")

    results: list[dict[str, Any]] = []
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            raise ValueError(f"samples[{index}] must be an object")
        package_name = sample.get("package_name")
        code = sample.get("code")
        if not isinstance(package_name, str) or not package_name.strip():
            raise ValueError(f"samples[{index}].package_name is required")
        if not isinstance(code, str):
            raise ValueError(f"samples[{index}].code must be a string")
        actual = _ground_truth(sample.get("ground_truth"))

        provenance = check_provenance(package_name)
        signature = check_signature(code, package_name)
        verdict = _jamp_verdict(provenance, signature)
        baseline = (
            "HALLUCINATION_CAUGHT"
            if provenance.get("status") == "NOT_FOUND"
            else "CLEAN"
            if provenance.get("evidence", {}).get("pypi_exists") is True
            else "INCONCLUSIVE"
        )
        results.append(
            {
                "sample_id": sample.get("sample_id", sample.get("id", f"sample-{index + 1:04d}")),
                "package_name": package_name,
                "ground_truth": "HALLUCINATION" if actual else "CLEAN",
                "actual_hallucination": actual,
                "baseline_verdict": baseline,
                "jamp_verdict": verdict,
                "provenance": provenance,
                "signature": signature,
            }
        )

    paired = [
        row for row in results
        if row["baseline_verdict"] in DEFINITIVE_PREDICTIONS
        and row["jamp_verdict"] in DEFINITIVE_PREDICTIONS
    ]
    jamp_only = sum(
        (row["jamp_verdict"] == "HALLUCINATION_CAUGHT") == row["actual_hallucination"]
        and (row["baseline_verdict"] == "HALLUCINATION_CAUGHT") != row["actual_hallucination"]
        for row in paired
    )
    baseline_only = sum(
        (row["baseline_verdict"] == "HALLUCINATION_CAUGHT") == row["actual_hallucination"]
        and (row["jamp_verdict"] == "HALLUCINATION_CAUGHT") != row["actual_hallucination"]
        for row in paired
    )
    report = {
        "schema_version": "jamp-hunt-evaluation-v0.3",
        "evidence_class": payload.get("evidence_class", "UNSPECIFIED_INPUT")
        if isinstance(payload, dict) else "UNSPECIFIED_INPUT",
        "input_sha256": hashlib.sha256(raw_input).hexdigest(),
        "attempted_sample_count": len(results),
        "baseline": _accuracy(results, "baseline_verdict"),
        "jamp": _accuracy(results, "jamp_verdict"),
        "inconclusive_count": sum(row["jamp_verdict"] == "INCONCLUSIVE" for row in results),
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
    parser.add_argument("--input", required=True, type=Path, help="JSON file with LLM samples")
    parser.add_argument(
        "--output", type=Path, default=Path("results_v0.3.json"),
        help="output report path (default: results_v0.3.json)",
    )
    args = parser.parse_args()
    report = evaluate(args.input, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "attempted_sample_count": report["attempted_sample_count"],
                "paired_scored_count": report["paired_scored_count"],
                "inconclusive_count": report["inconclusive_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
