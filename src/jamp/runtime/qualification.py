from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# This file is populated by the benchmark harness at runtime. A measurement must
# be reviewed and committed separately before it becomes runtime qualification evidence.
MEASURED_BENCHMARKS_PATH = Path(__file__).with_name("measured_benchmarks.json")

# Explicit reviewed entries remain supported; unrecorded pairs fail closed.
QUALIFICATION_REGISTRY: dict[tuple[str, str], str] = {
    ("z-ai/glm-5.3-flash", "search_and_extraction"): "UNKNOWN",
}

MINIMUM_SCORE = 0.9
EXPECTED_CASE_COUNT = 5


def _load_measured_benchmark_result(model_id: str, task_type: str) -> dict[str, Any] | None:
    try:
        document: Any = json.loads(MEASURED_BENCHMARKS_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    model_record = document.get(model_id)
    if not isinstance(model_record, dict):
        return None
    result = model_record.get(task_type)
    return result if isinstance(result, dict) else None


def _measured_benchmark_qualifies(
    result: dict[str, Any], model_id: str, required_benchmark_version: str
) -> bool:
    score = result.get("score")
    case_count = result.get("case_count")
    passed_cases = result.get("passed_cases")
    actual_ids = result.get("actual_provider_model_ids")
    digest = result.get("benchmark_data_sha256")
    timestamp = result.get("timestamp")

    # Do not trust the status label alone. Require a complete, exact-model,
    # version-matched, all-cases-passed record with E2 verification and a dataset digest.
    return (
        result.get("benchmark_version") == required_benchmark_version
        and result.get("status") == "QUALIFIED"
        and isinstance(score, (int, float))
        and not isinstance(score, bool)
        and MINIMUM_SCORE <= score <= 1.0
        and case_count == EXPECTED_CASE_COUNT
        and passed_cases == EXPECTED_CASE_COUNT
        and isinstance(actual_ids, list)
        and len(actual_ids) == EXPECTED_CASE_COUNT
        and all(item == model_id for item in actual_ids)
        and result.get("all_e2_verified") is True
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        and isinstance(timestamp, str)
        and bool(timestamp.strip())
    )


def evaluate_model_qualification(
    model_id: str, task_type: str, required_benchmark_version: str = "v1"
) -> str:
    """Return qualification only for exact model/task/version measured evidence.

    Missing, malformed, partial, version-mismatched, or inconsistent measurement
    records fail closed to UNKNOWN. A successful single request never qualifies
    a model. Registry fallback is only used when no measured record exists.
    """
    if not isinstance(model_id, str) or not model_id:
        return "UNKNOWN"
    if not isinstance(task_type, str) or not task_type:
        return "UNKNOWN"
    if not isinstance(required_benchmark_version, str) or not required_benchmark_version:
        return "UNKNOWN"

    result = _load_measured_benchmark_result(model_id, task_type)
    if result is not None:
        if result.get("benchmark_version") != required_benchmark_version:
            return "UNKNOWN"
        return (
            "QUALIFIED"
            if _measured_benchmark_qualifies(result, model_id, required_benchmark_version)
            else "UNKNOWN"
        )

    status = QUALIFICATION_REGISTRY.get((model_id, task_type), "UNKNOWN")
    return status if status in {"QUALIFIED", "UNKNOWN"} else "UNKNOWN"
