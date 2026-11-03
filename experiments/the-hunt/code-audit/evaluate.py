"""Paired Baseline/JAMP checks for the synthetic The Hunt fixture.

PyPI 404 means only "not found on PyPI at retrieval time"; it is not proof
that a package cannot exist on another index or under another distribution name.
A PyPI 200 establishes registry presence only, not package safety or API validity.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PYPI_API_URL = "https://pypi.org/pypi/{package}/json"
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
    """Apply a small explicit alias map and PEP 503-style name normalization."""
    candidate = MODULE_DISTRIBUTION_ALIASES.get(module, module)
    return re.sub(r"[-_.]+", "-", candidate).lower()


def baseline_check(code_str: str) -> str:
    """Naive baseline: valid Python with at least one import is CLEAN."""
    try:
        tree = ast.parse(_clean_code(code_str))
    except SyntaxError:
        return "SYNTAX_ERROR"
    return "CLEAN" if _imports(tree) else "NO_IMPORTS"


def _pypi_lookup(package: str, cache: dict[str, str]) -> str:
    """Return OBSERVED PyPI registry status; transport failures remain unknown."""
    if package in cache:
        return cache[package]

    url = PYPI_API_URL.format(package=quote(package, safe=""))
    request = Request(url, headers={"User-Agent": "JAMP-The-Hunt/0.1"})
    try:
        with urlopen(request, timeout=5) as response:
            if response.status == 200:
                payload = json.loads(response.read())
                if not isinstance(payload, dict) or not isinstance(payload.get("info"), dict):
                    result = "INCONCLUSIVE"
                else:
                    result = "EXISTS_ON_PYPI"
            else:
                result = "INCONCLUSIVE"
    except HTTPError as error:
        result = "NOT_FOUND_ON_PYPI" if error.code == 404 else "INCONCLUSIVE"
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        result = "INCONCLUSIVE"

    cache[package] = result
    return result


def jamp_v2_check(code_str: str, cache: dict[str, str]) -> str:
    """Check syntax, selected risky calls, then imported names against PyPI."""
    try:
        tree = ast.parse(_clean_code(code_str))
    except SyntaxError:
        return "SYNTAX_ERROR"

    if _has_suspicious_calls(tree):
        return "SUSPICIOUS_AST"

    imports = _imports(tree)
    packages = sorted(
        _distribution_name(module)
        for module in imports
        if module not in STDLIB_MODULES
    )
    if not packages:
        return "NO_EXTERNAL_IMPORTS"

    for package in packages:
        status = _pypi_lookup(package, cache)
        if status == "NOT_FOUND_ON_PYPI":
            return f"PACKAGE_NOT_FOUND_ON_PYPI ({package})"
        if status == "INCONCLUSIVE":
            return f"INCONCLUSIVE ({package})"

    return "PACKAGE_EXISTS_ONLY"


def _correctness(verdict: str, is_fake: bool, engine: str) -> bool | None:
    """Score only outcomes supported by the registry check and supplied labels."""
    if verdict == "SYNTAX_ERROR" or verdict.startswith("INCONCLUSIVE"):
        return None
    if engine == "baseline":
        if verdict == "NO_IMPORTS":
            return None
        return (verdict == "SYNTAX_ERROR") if is_fake else verdict == "CLEAN"
    if verdict == "SUSPICIOUS_AST":
        return None
    if verdict.startswith("PACKAGE_NOT_FOUND_ON_PYPI"):
        return is_fake
    if verdict == "PACKAGE_EXISTS_ONLY":
        return None if is_fake else True
    return None


def evaluate() -> dict[str, Any]:
    """Evaluate the same saved LLM outputs with both engines (paired comparison)."""
    path = Path(__file__).parent / "llm_responses.json"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not found. Generate it first.")

    tasks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("llm_responses.json must contain a JSON array.")

    cache: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    started = time.perf_counter()

    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError("Each response entry must be a JSON object.")
        task_id = task.get("task_id")
        ground_truth = task.get("ground_truth")
        code = task.get("llm_output")
        if not isinstance(task_id, str) or not isinstance(ground_truth, dict):
            raise ValueError("Each entry requires task_id and ground_truth object.")
        if not isinstance(code, str) or not code.strip():
            results.append({"task_id": task_id, "status": "INCONCLUSIVE_MISSING_OUTPUT"})
            continue
        is_fake = ground_truth.get("is_hallucinated")
        if not isinstance(is_fake, bool):
            raise ValueError(f"{task_id}: ground_truth.is_hallucinated must be boolean.")

        baseline = baseline_check(code)
        jamp = jamp_v2_check(code, cache)
        results.append(
            {
                "task_id": task_id,
                "is_fake": is_fake,
                "baseline": baseline,
                "baseline_correct": _correctness(baseline, is_fake, "baseline"),
                "jamp": jamp,
                "jamp_correct": _correctness(jamp, is_fake, "jamp"),
            }
        )

    elapsed = time.perf_counter() - started
    baseline_scored = [item for item in results if item.get("baseline_correct") is not None]
    jamp_scored = [item for item in results if item.get("jamp_correct") is not None]
    report: dict[str, Any] = {
        "evidence_class": "SYNTHETIC_FIXTURE_WITH_LIVE_PYPI_OBSERVATIONS",
        "pypi_lookup_count": len(cache),
        "elapsed_seconds": round(elapsed, 3),
        "baseline": {
            "correct": sum(bool(item["baseline_correct"]) for item in baseline_scored),
            "scored": len(baseline_scored),
        },
        "jamp": {
            "correct": sum(bool(item["jamp_correct"]) for item in jamp_scored),
            "scored": len(jamp_scored),
        },
        "unscored_or_conflicted": sum(
            item.get("baseline_correct") is None or item.get("jamp_correct") is None
            for item in results
        ),
        "results": results,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


if __name__ == "__main__":
    evaluate()
