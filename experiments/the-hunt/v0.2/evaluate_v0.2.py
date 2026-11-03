"""Strict paired evaluation for The Hunt Benchmark v0.2.

The evaluator never calls the network. Ground Truth is used only by the scoring
layer. Baseline and JAMP receive the same immutable input_context object.
JAMP's local registry cache must be a separately acquired evidence artifact,
not copied from observations.jsonl or the Ground Truth raw-response directory.
Synthetic fixture inputs are explicitly labelled SYNTHETIC_CONTROL_INPUT and
must not be described as measured real-LLM hallucinations.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFINITIVE_GT = {"EXISTS_ON_PYPI", "NOT_FOUND_ON_PYPI"}
ALL_GT = DEFINITIVE_GT | {"INCONCLUSIVE", "AMBIGUOUS"}
POSITIVE_CLASS = "HALLUCINATED_PACKAGE"
Z_95 = 1.959963984540054
ALPHA = 0.05


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def verify_ground_truth_lock(gt_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = gt_dir / "manifest.json"
    observations_path = gt_dir / "observations.jsonl"
    checksums_path = gt_dir / "checksums.sha256"
    for path in (manifest_path, observations_path, checksums_path):
        if not path.is_file():
            raise FileNotFoundError(f"Ground Truth Lock file missing: {path}")

    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != "jamp-hunt-ground-truth-v0.2":
        raise ValueError("Unsupported Ground Truth schema")
    if manifest.get("evidence_class") != "LIVE_REGISTRY_OBSERVATIONS":
        raise ValueError("Ground Truth manifest has unexpected evidence_class")
    if manifest.get("collection_complete") is not True:
        raise ValueError("Ground Truth collection is not marked complete")
    if manifest.get("candidate_count") != 200:
        raise ValueError("The Hunt v0.2 Ground Truth Lock must contain exactly 200 candidates")
    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("Ground Truth manifest is missing source snapshot metadata")
    snapshot_path = gt_dir / str(source.get("retrieved_snapshot_path", ""))
    if (
        not snapshot_path.is_file()
        or sha256_bytes(snapshot_path.read_bytes()) != source.get("snapshot_sha256")
    ):
        raise ValueError("Pinned Top PyPI source snapshot is missing or has a digest mismatch")

    observations_bytes = observations_path.read_bytes()
    expected_observations_hash = manifest.get("observations_file_sha256")
    if sha256_bytes(observations_bytes) != expected_observations_hash:
        raise ValueError("observations.jsonl SHA-256 does not match manifest")

    checksums_bytes = checksums_path.read_bytes()
    if sha256_bytes(checksums_bytes) != manifest.get("checksums_file_sha256"):
        raise ValueError("checksums.sha256 digest does not match manifest")

    checksummed_paths: set[str] = set()
    for line in checksums_bytes.decode("utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative_path = line.split("  ", 1)
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "raw_responses":
            raise ValueError(f"Unsafe raw evidence path: {relative_path}")
        raw_path = gt_dir / relative
        if not raw_path.is_file() or sha256_bytes(raw_path.read_bytes()) != digest:
            raise ValueError(f"Raw evidence checksum mismatch: {relative_path}")
        checksummed_paths.add(relative.as_posix())

    actual_raw_paths = {
        path.relative_to(gt_dir).as_posix()
        for path in (gt_dir / "raw_responses").glob("*.json")
    }
    if actual_raw_paths != checksummed_paths:
        raise ValueError("Raw response directory and checksums.sha256 file set differ")

    observations = load_jsonl(observations_path)
    if len(observations) != 200:
        raise ValueError("Ground Truth observations must contain exactly 200 rows")
    seen_names: set[str] = set()
    observed_counts = {state: 0 for state in ALL_GT}
    for item in observations:
        if item.get("status") not in ALL_GT:
            raise ValueError(f"Unknown Ground Truth status: {item.get('status')!r}")
        name = item.get("normalized_name")
        if not isinstance(name, str) or normalize_distribution_name(name) != name:
            raise ValueError("Observation has missing or non-normalized distribution name")
        if name in seen_names:
            raise ValueError(f"Duplicate normalized Ground Truth name: {name}")
        seen_names.add(name)
        observed_counts[item["status"]] += 1
        digest = item.get("raw_response_sha256")
        raw_relative = item.get("raw_response_path")
        if digest is None:
            if raw_relative is not None:
                raise ValueError("Raw response path exists without a response digest")
            if item.get("status") in DEFINITIVE_GT:
                raise ValueError("Definitive observation is missing raw response digest")
        else:
            if not isinstance(raw_relative, str):
                raise ValueError("Raw response digest has no corresponding file path")
            raw_relative_path = Path(raw_relative)
            if (
                raw_relative_path.is_absolute()
                or ".." in raw_relative_path.parts
                or raw_relative_path.as_posix() not in checksummed_paths
            ):
                raise ValueError("Observation raw response path is unsafe or unchecksummed")
            raw_file = gt_dir / raw_relative_path
            if not raw_file.is_file() or sha256_bytes(raw_file.read_bytes()) != digest:
                raise ValueError(f"Observation raw response digest mismatch: {raw_relative}")
    if observed_counts != manifest.get("status_counts"):
        raise ValueError("Manifest status counts differ from observations")
    return manifest, observations


def parse_imports(source_code: str) -> set[str]:
    tree = ast.parse(source_code)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def wilson_interval(successes: int, trials: int, z: float = Z_95) -> list[float] | None:
    if trials == 0:
        return None
    if not 0 <= successes <= trials:
        raise ValueError("Wilson inputs require 0 <= successes <= trials")
    proportion = successes / trials
    z2 = z * z
    denominator = 1.0 + z2 / trials
    center = (proportion + z2 / (2.0 * trials)) / denominator
    margin = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z2 / (4.0 * trials * trials)
        )
        / denominator
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def binary_metrics(actual: list[bool], predicted: list[bool]) -> dict[str, Any]:
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted vectors must have identical lengths")
    tp = sum(a and p for a, p in zip(actual, predicted, strict=True))
    tn = sum((not a) and (not p) for a, p in zip(actual, predicted, strict=True))
    fp = sum((not a) and p for a, p in zip(actual, predicted, strict=True))
    fn = sum(a and (not p) for a, p in zip(actual, predicted, strict=True))
    total = tp + tn + fp + fn
    return {
        "positive_class": POSITIVE_CLASS,
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "accuracy": (tp + tn) / total if total else None,
        "accuracy_wilson_95_ci": wilson_interval(tp + tn, total),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "scored_count": total,
    }


def exact_mcnemar(b: int, c: int) -> float:
    """Exact two-sided binomial McNemar p-value, no asymptotic approximation."""
    if b < 0 or c < 0:
        raise ValueError("Discordant counts cannot be negative")
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def load_jamp_cache(path: Path, gt_manifest: dict[str, Any]) -> dict[str, str]:
    cache = load_json(path)
    if cache.get("evidence_class") != "JAMP_INDEPENDENT_REGISTRY_CACHE":
        raise ValueError(
            "JAMP cache must be a separately acquired "
            "JAMP_INDEPENDENT_REGISTRY_CACHE artifact"
        )
    if cache.get("ground_truth_source_observations_sha256") == gt_manifest.get(
        "observations_file_sha256"
    ):
        raise ValueError("JAMP cache is derived from the Ground Truth snapshot (circular)")
    if cache.get("acquired_before_ground_truth_reveal") is not True:
        raise ValueError("JAMP cache must attest it was acquired before GT reveal")
    entries = cache.get("packages")
    if not isinstance(entries, dict):
        raise ValueError("JAMP cache must contain a packages object")
    normalized: dict[str, str] = {}
    for name, status in entries.items():
        key = normalize_distribution_name(name)
        if status not in ALL_GT:
            raise ValueError(f"Invalid JAMP cache status for {name}: {status!r}")
        if key in normalized:
            raise ValueError(f"Duplicate normalized cache key: {key}")
        normalized[key] = status
    return normalized


def baseline_predict(input_context: dict[str, Any]) -> dict[str, Any]:
    source_code = input_context["source_code"]
    imports = parse_imports(source_code)
    mapping = input_context["import_distribution_map"]
    mapped = sorted({normalize_distribution_name(mapping[module]) for module in imports if module in mapping})
    if not mapped:
        return {"status": "INVALID_UNSCORABLE", "prediction_hallucinated": None, "imports": sorted(imports)}
    # Syntax-only negative control: valid syntax plus a mapped target import
    # always predicts that the imported package exists.
    return {
        "status": "CLEAN",
        "prediction_hallucinated": False,
        "imports": sorted(imports),
        "mapped_distributions": mapped,
    }


def jamp_predict(input_context: dict[str, Any], cache: dict[str, str]) -> dict[str, Any]:
    imports = parse_imports(input_context["source_code"])
    mapping = input_context["import_distribution_map"]
    mapped = sorted({normalize_distribution_name(mapping[module]) for module in imports if module in mapping})
    if not mapped:
        return {"status": "INVALID_UNSCORABLE", "prediction_hallucinated": None}
    statuses = {name: cache.get(name, "INCONCLUSIVE") for name in mapped}
    if any(value in {"INCONCLUSIVE", "AMBIGUOUS"} for value in statuses.values()):
        return {
            "status": "INCONCLUSIVE",
            "prediction_hallucinated": None,
            "registry_statuses": statuses,
        }
    not_found = sorted(name for name, value in statuses.items() if value == "NOT_FOUND_ON_PYPI")
    return {
        "status": "PACKAGE_NOT_FOUND_ON_PYPI" if not_found else "PACKAGE_EXISTS_ONLY",
        "prediction_hallucinated": bool(not_found),
        "registry_statuses": statuses,
    }


def evaluate(gt_dir: Path, tasks_path: Path, cache_path: Path, output_path: Path) -> dict[str, Any]:
    gt_manifest, gt_rows = verify_ground_truth_lock(gt_dir)
    gt_by_name = {row["normalized_name"]: row for row in gt_rows}
    cache = load_jamp_cache(cache_path, gt_manifest)
    tasks = load_jsonl(tasks_path)
    if not tasks:
        raise ValueError("Paired evaluation requires at least one task")

    predictions: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []
    baseline_actual: list[bool] = []
    baseline_predicted: list[bool] = []
    jamp_actual: list[bool] = []
    jamp_predicted: list[bool] = []
    task_ids: set[str] = set()

    for task in tasks:
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or task_id in task_ids:
            raise ValueError("Each task must have a unique task_id")
        task_ids.add(task_id)
        if task.get("input_origin") != "SYNTHETIC_CONTROL_INPUT":
            raise ValueError(f"{task_id}: input_origin must be SYNTHETIC_CONTROL_INPUT")
        context = task.get("input_context")
        if (
            not isinstance(context, dict)
            or not isinstance(context.get("source_code"), str)
            or not isinstance(context.get("prompt_text"), str)
        ):
            raise ValueError(f"{task_id}: input_context requires prompt_text and source_code")
        mapping = context.get("import_distribution_map")
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError(f"{task_id}: missing import_distribution_map")
        input_hash = sha256_bytes(
            json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        prompt_hash = sha256_bytes(context["prompt_text"].encode("utf-8"))
        model_output_hash = sha256_bytes(context["source_code"].encode("utf-8"))

        try:
            baseline = baseline_predict(context)
            jamp = jamp_predict(context, cache)
        except (SyntaxError, KeyError, TypeError) as exc:
            exclusions.append({"task_id": task_id, "reason": f"INVALID_INPUT_CONTEXT: {type(exc).__name__}"})
            continue

        imported_modules = parse_imports(context["source_code"])
        mapped_names = sorted(
            {
                normalize_distribution_name(mapping[module])
                for module in imported_modules
                if module in mapping
            }
        )
        missing_gt = [name for name in mapped_names if name not in gt_by_name]
        if missing_gt:
            exclusions.append({"task_id": task_id, "reason": f"GROUND_TRUTH_MISSING: {','.join(missing_gt)}"})
            continue
        gt_statuses = {name: gt_by_name[name]["status"] for name in mapped_names}
        if any(value in {"INCONCLUSIVE", "AMBIGUOUS"} for value in gt_statuses.values()):
            reason = "GROUND_TRUTH_" + (
                "AMBIGUOUS" if "AMBIGUOUS" in gt_statuses.values() else "INCONCLUSIVE"
            )
            exclusions.append({"task_id": task_id, "reason": reason})
            continue
        if baseline["prediction_hallucinated"] is None or jamp["prediction_hallucinated"] is None:
            exclusions.append({"task_id": task_id, "reason": "UNSCORABLE_PREDICTION"})
            continue

        actual_hallucinated = any(value == "NOT_FOUND_ON_PYPI" for value in gt_statuses.values())
        baseline_actual.append(actual_hallucinated)
        baseline_predicted.append(bool(baseline["prediction_hallucinated"]))
        jamp_actual.append(actual_hallucinated)
        jamp_predicted.append(bool(jamp["prediction_hallucinated"]))
        predictions.append(
            {
                "task_id": task_id,
                "input_context_sha256": input_hash,
                "prompt_sha256": prompt_hash,
                "model_output_sha256": model_output_hash,
                "ground_truth_statuses": gt_statuses,
                "actual_hallucinated": actual_hallucinated,
                "baseline": baseline,
                "jamp": jamp,
                "scored_pair": True,
            }
        )

    baseline_correct = [
        actual == predicted for actual, predicted in zip(baseline_actual, baseline_predicted, strict=True)
    ]
    jamp_correct = [
        actual == predicted for actual, predicted in zip(jamp_actual, jamp_predicted, strict=True)
    ]
    b = sum(j and not base for j, base in zip(jamp_correct, baseline_correct, strict=True))
    c = sum(base and not j for j, base in zip(jamp_correct, baseline_correct, strict=True))

    report = {
        "schema_version": "jamp-hunt-paired-evaluation-v0.2",
        "evidence_class": "SYNTHETIC_CONTROL_EVALUATION",
        "input_origin": "SYNTHETIC_CONTROL_INPUT",
        "interpretation_limit": (
            "Synthetic control inputs are not real LLM outputs and do not measure "
            "real-world LLM hallucination frequency or general JAMP superiority."
        ),
        "input_hash_contract": {
            "paired_input_context": "canonical JSON SHA-256",
            "prompt_text": "UTF-8 SHA-256",
            "synthetic_model_output_source_code": "UTF-8 SHA-256",
        },
        "ground_truth_manifest_sha256": sha256_bytes((gt_dir / "manifest.json").read_bytes()),
        "ground_truth_observations_sha256": gt_manifest["observations_file_sha256"],
        "tasks_file_sha256": sha256_bytes(tasks_path.read_bytes()),
        "jamp_cache_file_sha256": sha256_bytes(cache_path.read_bytes()),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "attempted_task_count": len(tasks),
        "paired_scored_count": len(predictions),
        "excluded_task_count": len(exclusions),
        "inconclusive_rate": len(exclusions) / len(tasks) if tasks else None,
        "coverage": len(predictions) / len(tasks) if tasks else None,
        "unscored_count_by_reason": {
            reason: sum(item["reason"] == reason for item in exclusions)
            for reason in sorted({item["reason"] for item in exclusions})
        },
        "excluded_tasks": exclusions,
        "baseline": binary_metrics(baseline_actual, baseline_predicted),
        "jamp": binary_metrics(jamp_actual, jamp_predicted),
        "paired_accuracy_difference_jamp_minus_baseline": (
            binary_metrics(jamp_actual, jamp_predicted)["accuracy"]
            - binary_metrics(baseline_actual, baseline_predicted)["accuracy"]
            if predictions else None
        ),
        "mcnemar_exact_two_sided": {
            "b_jamp_correct_baseline_incorrect": b,
            "c_jamp_incorrect_baseline_correct": c,
            "discordant_pairs": b + c,
            "p_value": exact_mcnemar(b, c),
            "alpha": ALPHA,
            "no_discordant_pairs": b + c == 0,
        },
        "predictions": predictions,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-dir", type=Path, default=Path("ground_truth"))
    parser.add_argument("--tasks", type=Path, required=True, help="Paired tasks JSONL")
    parser.add_argument("--jamp-cache", type=Path, required=True, help="Independent pre-GT JAMP cache JSON")
    parser.add_argument("--output", type=Path, default=Path("results/paired_evaluation.json"))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.ground_truth_dir, args.tasks, args.jamp_cache, args.output), indent=2))


if __name__ == "__main__":
    main()
