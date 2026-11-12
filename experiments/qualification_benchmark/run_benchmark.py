from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "experiments/qualification_benchmark/benchmark_data.json"
OUTPUT_PATH = ROOT / "src/jamp/runtime/measured_benchmarks.json"
TARGET_MODEL = "z-ai/glm-5.3-flash"
TASK_TYPE = "search_and_extraction"
THRESHOLD = 0.9
BENCHMARK_VERSION = "v1"


def clean_quarter(value: Any) -> str | None:
    """Normalize quarter labels while preserving an optional year."""
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().lower()
    match = re.fullmatch(
        r"(?:q\s*)?([1-4])(?:\s*(?:quarter|квартал))?(?:\s+(\d{4}))?",
        text,
    )
    if match is None:
        match = re.fullmatch(r"(?:квартал\s*)?([1-4])(?:\s+(\d{4}))?", text)
    if match is None:
        return None
    quarter, year = match.groups()
    return f"{quarter}:{year}" if year else quarter


def clean_number(value: Any) -> int | float | None:
    """Normalize a number or currency-like string without guessing missing values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None

    cleaned = value.strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    cleaned = re.sub(r"(?i)\s*(?:руб(?:лей|ля|ль)?|руб\.?|usd|eur)\s*$", "", cleaned)
    multiplier = 1
    if cleaned.upper().endswith("M"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.upper().endswith("K"):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    try:
        number = float(cleaned.strip()) * multiplier
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def parse_model_json(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str):
        return None
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def values_match(expected: dict[str, Any], observed: dict[str, Any] | None) -> bool:
    if observed is None:
        return False
    for key, expected_value in expected.items():
        if key not in observed:
            return False
        if key == "quarter":
            expected_quarter = clean_quarter(expected_value)
            observed_quarter = clean_quarter(observed[key])
            if expected_quarter is None or observed_quarter is None:
                return False
            if expected_quarter != observed_quarter:
                return False
        elif isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
            if clean_number(observed[key]) != expected_value:
                return False
        elif observed[key] != expected_value:
            return False
    return True


def main() -> int:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("HOLD: OPENROUTER_API_KEY is not configured.", file=sys.stderr)
        return 2

    raw_data = DATA_PATH.read_bytes()
    cases = json.loads(raw_data)
    if not isinstance(cases, list) or len(cases) != 5:
        print("HOLD: benchmark dataset must contain exactly five cases.", file=sys.stderr)
        return 2

    os.environ.setdefault(
        "OPENROUTER_MODEL_ID_MAP",
        json.dumps({"am/nemotron-3-super-120b-a12b": TARGET_MODEL}),
    )
    os.environ.setdefault("JAMP_ENV", "local")
    from jamp.api.app import create_app

    records: list[dict[str, Any]] = []
    passed = 0
    observed_model_ids: list[str] = []

    with TestClient(create_app()) as client:
        for case in cases:
            prompt = (
                "Extract the financial facts from the source text. Return ONLY one JSON object, "
                "with no markdown and no explanation. Use exactly the keys in the reference task: "
                "quarter, revenue, net_income, operating_expenses as applicable. Numbers must be "
                "plain numeric values, not formatted strings. Do not infer facts not present.\n"
                f"Source text: {case['text']}\n"
                f"Required fields: {', '.join(case['expected'].keys())}"
            )
            response = client.post(
                "/v1/execute",
                json={
                    "intent": TASK_TYPE,
                    "prompt": prompt,
                    "request_id": f"qualification-benchmark:{case['id']}",
                },
            )
            body = (
                response.json()
                if response.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            output = body.get("output") if isinstance(body, dict) else None
            content = output.get("content") if isinstance(output, dict) else None
            actual_model = output.get("provider_model_id") if isinstance(output, dict) else None
            if isinstance(actual_model, str):
                observed_model_ids.append(actual_model)
            parsed = parse_model_json(content)
            matched = (
                response.status_code == 200
                and body.get("status") == "EXECUTE"
                and values_match(case["expected"], parsed)
            )
            if matched:
                passed += 1
            records.append(
                {
                    "case_id": case["id"],
                    "http_status": response.status_code,
                    "execution_status": body.get("status") if isinstance(body, dict) else None,
                    "evidence_status": (
                        body.get("evidence_status") if isinstance(body, dict) else None
                    ),
                    "provider_model_id": actual_model,
                    "expected": case["expected"],
                    "observed": parsed,
                    "matched": matched,
                    "trace_id": body.get("trace_id") if isinstance(body, dict) else None,
                }
            )
            print(f"{case['id']}: {'PASS' if matched else 'FAIL'}")

    score = passed / len(cases)
    exact_model = len(observed_model_ids) == len(cases) and all(
        model_id == TARGET_MODEL for model_id in observed_model_ids
    )
    all_e2_verified = all(record["evidence_status"] == "VERIFIED" for record in records)
    qualified_candidate = (
        score >= THRESHOLD and passed == len(cases) and exact_model and all_e2_verified
    )
    result = {
        TARGET_MODEL: {
            TASK_TYPE: {
                "score": score,
                "threshold": THRESHOLD,
                "model_id": TARGET_MODEL,
                "task_type": TASK_TYPE,
                "total_cases": len(cases),
                "dataset_sha256": hashlib.sha256(raw_data).hexdigest(),
                "status": "QUALIFIED" if qualified_candidate else "UNKNOWN",
                "measurement_status": "MEASURED",
                "timestamp": datetime.now(UTC).isoformat(),
                "benchmark_id": "synthetic_financial_extraction_v1",
                "benchmark_version": BENCHMARK_VERSION,
                "benchmark_data_sha256": hashlib.sha256(raw_data).hexdigest(),
                "case_count": len(cases),
                "passed_cases": passed,
                "actual_provider_model_ids": observed_model_ids,
                "all_e2_verified": all_e2_verified,
                "qualification_basis": (
                    "five live API executions; exact model identity; "
                    "all cases and E2 checks must pass"
                ),
                "cases": records,
            }
        }
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "score": score,
                "passed_cases": passed,
                "case_count": len(cases),
                "actual_model_identity_match": exact_model,
                "all_e2_verified": all_e2_verified,
                "candidate_status": result[TARGET_MODEL][TASK_TYPE]["status"],
                "output_path": str(OUTPUT_PATH.relative_to(ROOT)),
            },
            ensure_ascii=False,
        )
    )
    return 0 if qualified_candidate else 1


if __name__ == "__main__":
    raise SystemExit(main())
