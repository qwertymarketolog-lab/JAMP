"""Paired Baseline/JAMP comparison against observed PyPI registry ground truth.

The target is distribution-name presence on PyPI at a recorded observation time.
It is not a claim about global package existence, package safety, or API validity.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

STDLIB_MODULES = sys.stdlib_module_names
MODULE_DISTRIBUTION_ALIASES = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "yaml": "PyYAML",
}


def _clean_code(code: str) -> str:
    """Remove one optional Markdown code fence without changing code content."""
    cleaned = code.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return cleaned


def _imports(tree: ast.AST) -> set[str]:
    """Return imported top-level module names."""
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def _has_suspicious_calls(tree: ast.AST) -> bool:
    """Detect selected dynamic-import and code-execution calls structurally."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id in {
            "__import__",
            "eval",
            "exec",
            "import_module",
        }:
            return True
        if isinstance(function, ast.Attribute) and function.attr in {
            "import_module",
            "system",
        }:
            return True
    return False


def _distribution_name(module: str) -> str:
    """Apply explicit module aliases and PEP 503-style name normalization."""
    candidate = MODULE_DISTRIBUTION_ALIASES.get(module, module)
    return re.sub(r"[-_.]+", "-", candidate).lower()


def baseline_check(code_str: str) -> str:
    """Naive baseline: valid Python with at least one import is CLEAN."""
    try:
        tree = ast.parse(_clean_code(code_str))
    except SyntaxError:
        return "SYNTAX_ERROR"
    return "CLEAN" if _imports(tree) else "NO_IMPORTS"


def jamp_v2_check(code_str: str, observations: dict[str, str]) -> str:
    """Check syntax, selected risky calls, then imports against observed PyPI data."""
    try:
        tree = ast.parse(_clean_code(code_str))
    except SyntaxError:
        return "SYNTAX_ERROR"

    if _has_suspicious_calls(tree):
        return "SUSPICIOUS_AST"

    packages = sorted(
        _distribution_name(module)
        for module in _imports(tree)
        if module not in STDLIB_MODULES
    )
    if not packages:
        return "NO_EXTERNAL_IMPORTS"

    for package in packages:
        status = observations.get(package, "INCONCLUSIVE")
        if status == "NOT_FOUND_ON_PYPI":
            return f"PACKAGE_NOT_FOUND_ON_PYPI ({package})"
        if status != "EXISTS_ON_PYPI":
            return f"INCONCLUSIVE ({package})"

    return "PACKAGE_EXISTS_ONLY"


def _baseline_prediction(verdict: str) -> bool | None:
    """Baseline accepts any import as evidence that the package exists."""
    if verdict == "CLEAN":
        return True
    return None


def _jamp_prediction(verdict: str) -> bool | None:
    """Map only registry-presence verdicts to a binary prediction."""
    if verdict == "PACKAGE_EXISTS_ONLY":
        return True
    if verdict.startswith("PACKAGE_NOT_FOUND_ON_PYPI"):
        return False
    return None


def _accuracy(predictions: list[tuple[bool, bool]]) -> dict[str, Any]:
    """Calculate accuracy over the exact same paired observations."""
    correct = sum(predicted == actual for predicted, actual in predictions)
    count = len(predictions)
    return {
        "correct": correct,
        "scored": count,
        "accuracy": round(correct / count, 4) if count else None,
    }


def evaluate() -> dict[str, Any]:
    """Evaluate identical fixture inputs with strict paired scoring."""
    directory = Path(__file__).parent
    tasks_path = directory / "llm_responses.json"
    ground_truth_path = directory / "ground_truth.json"
    if not tasks_path.exists():
        raise FileNotFoundError(f"{tasks_path.name} not found.")
    if not ground_truth_path.exists():
        raise FileNotFoundError(
            f"{ground_truth_path.name} not found; run verify_ground_truth.py first."
        )

    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("llm_responses.json must contain a JSON array.")
    if ground_truth.get("schema_version") != "jamp-hunt-ground-truth-v1":
        raise ValueError("Unsupported ground_truth.json schema_version.")

    observed_status = {
        item["normalized_name"]: item["status"]
        for item in ground_truth.get("observations", [])
        if isinstance(item, dict)
        and isinstance(item.get("normalized_name"), str)
        and isinstance(item.get("status"), str)
    }

    results: list[dict[str, Any]] = []
    baseline_pairs: list[tuple[bool, bool]] = []
    jamp_pairs: list[tuple[bool, bool]] = []
    started = time.perf_counter()

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each response entry must be a JSON object.")
        task_id = task.get("task_id")
        code = task.get("llm_output")
        package = task.get("package_under_test")
        task_type = task.get("type")
        if not isinstance(task_id, str) or not isinstance(package, str):
            raise ValueError("Each task requires task_id and package_under_test.")
        if not isinstance(code, str) or not code.strip():
            results.append(
                {"task_id": task_id, "status": "INCONCLUSIVE_EMPTY_OUTPUT",
                 "baseline": "INCONCLUSIVE", "jamp": "INCONCLUSIVE"}
            )
            continue

        normalized = re.sub(r"[-_.]+", "-", package).lower()
        registry_status = observed_status.get(normalized, "INCONCLUSIVE")
        expected_status = {
            "normal": "EXISTS_ON_PYPI",
            "trap": "NOT_FOUND_ON_PYPI",
        }.get(task_type)
        if expected_status is None:
            raise ValueError(f"{task_id}: unsupported fixture type {task_type!r}.")

        baseline = baseline_check(code)
        jamp = jamp_v2_check(code, observed_status)
        if registry_status != expected_status:
            results.append(
                {
                    "task_id": task_id,
                    "package_under_test": package,
                    "registry_status": registry_status,
                    "status": "GROUND_TRUTH_CONFLICT_OR_INCONCLUSIVE",
                    "baseline": baseline,
                    "jamp": jamp,
                    "baseline_prediction": None,
                    "jamp_prediction": None,
                    "scored_pair": False,
                }
            )
            continue

        actual_exists = registry_status == "EXISTS_ON_PYPI"
        baseline_prediction = _baseline_prediction(baseline)
        jamp_prediction = _jamp_prediction(jamp)
        paired = baseline_prediction is not None and jamp_prediction is not None
        if paired:
            baseline_pairs.append((baseline_prediction, actual_exists))
            jamp_pairs.append((jamp_prediction, actual_exists))

        results.append(
            {
                "task_id": task_id,
                "package_under_test": package,
                "registry_status": registry_status,
                "ground_truth_scope": "PyPI distribution presence at observation time",
                "status": "SCORED_PAIR" if paired else "INCONCLUSIVE_FOR_BOTH",
                "baseline": baseline,
                "jamp": jamp,
                "baseline_prediction": baseline_prediction,
                "jamp_prediction": jamp_prediction,
                "actual_package_exists": actual_exists,
                "scored_pair": paired,
            }
        )

    report: dict[str, Any] = {
        "evidence_class": "SYNTHETIC_FIXTURE_WITH_LIVE_PYPI_GROUND_TRUTH",
        "ground_truth_observed_at_utc": ground_truth.get("observed_at_utc"),
        "ground_truth_scope": "PyPI distribution presence only; not global non-existence or safety",
        "task_count": len(tasks),
        "paired_scored_count": len(baseline_pairs),
        "unscored_or_conflicted_count": sum(not item.get("scored_pair", False) for item in results),
        "baseline": _accuracy(baseline_pairs),
        "jamp": _accuracy(jamp_pairs),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


if __name__ == "__main__":
    evaluate()
