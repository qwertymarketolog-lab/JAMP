#!/usr/bin/env python3
"""Compare two AnyModel N=3 availability evidence artifacts.

Read-only comparative audit: no API requests and no runtime/Frozen Core changes.
Attempts are aligned by their explicit attempt number, never by latency.
Structural verification is kept separate from availability repeatability.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

RUN1 = Path("artifacts/research/anymodel_availability_n3.json")
RUN2 = Path("artifacts/research/anymodel_availability_n3_run2.json")


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def get_model_id(row: dict[str, Any]) -> str:
    for key in ("model_id", "model", "id"):
        value = row.get(key)
        if isinstance(value, str):
            return value
    catalog_entry = row.get("catalog_entry")
    if isinstance(catalog_entry, dict):
        for key in ("model_id", "id", "model"):
            value = catalog_entry.get(key)
            if isinstance(value, str):
                return value
    raise KeyError(f"Cannot find model id; keys={list(row)}")


def get_attempts(row: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("attempts", "probes", "observations", "results"):
        value = row.get(key)
        if isinstance(value, list):
            return value
    return []


def normalize_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    """Map both artifact schemas to comparable per-attempt fields."""
    transport = attempt.get("transport")
    if isinstance(transport, dict):
        status_code = transport.get("status_code")
        timed_out = transport.get("timed_out")
        elapsed_ms = transport.get("elapsed_ms")
        error = None
        response = attempt.get("response")
        if isinstance(response, dict):
            error = response.get("error")
    else:
        status_code = attempt.get("http_status")
        error = attempt.get("error")
        error_text = str(error).lower() if error is not None else ""
        timed_out = ("timeout" in error_text or "timed out" in error_text)
        elapsed_ms = attempt.get("elapsed_ms")

    attempt_number = attempt.get("attempt")
    if attempt_number is not None:
        attempt_number = int(attempt_number)

    return {
        "attempt": attempt_number,
        "status_code": status_code,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "error": error,
    }


def normalize(document: dict[str, Any]) -> dict[str, dict[int, dict[str, Any]]]:
    rows = (
        document.get("results")
        if isinstance(document.get("results"), list)
        else document.get("models")
    )
    if not isinstance(rows, list):
        raise RuntimeError(f"Unknown artifact structure: top-level keys={list(document)}")

    normalized: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        model_id = get_model_id(row)
        attempts_by_number: dict[int, dict[str, Any]] = {}
        for raw_attempt in get_attempts(row):
            attempt = normalize_attempt(raw_attempt)
            number = attempt["attempt"]
            if number is None:
                raise ValueError(f"{model_id}: attempt is missing attempt number")
            if number in attempts_by_number:
                raise ValueError(f"{model_id}: duplicate attempt number {number}")
            attempts_by_number[number] = attempt
        normalized[model_id] = attempts_by_number
    return normalized


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def median_latency(attempts: dict[int, dict[str, Any]]) -> float | None:
    values = [
        item["elapsed_ms"]
        for item in attempts.values()
        if isinstance(item.get("elapsed_ms"), (int, float))
    ]
    return round(statistics.median(values), 1) if values else None


def status_counts(data: dict[str, dict[int, dict[str, Any]]]) -> Counter[str]:
    return Counter(
        "NO_STATUS" if attempt.get("status_code") is None else str(attempt["status_code"])
        for attempts in data.values()
        for attempt in attempts.values()
    )


def classify(
    run1: dict[int, dict[str, Any]],
    run2: dict[int, dict[str, Any]],
) -> str:
    labels: list[str] = []
    numbers1, numbers2 = set(run1), set(run2)
    common = sorted(numbers1 & numbers2)

    if numbers1 != numbers2:
        labels.append("ATTEMPT_SET_CHANGED")

    changed = any(
        run1[number].get("status_code") != run2[number].get("status_code")
        or run1[number].get("timed_out") != run2[number].get("timed_out")
        for number in common
    )
    if changed:
        labels.append("HTTP_OR_TIMEOUT_SIGNATURE_CHANGED_BY_ATTEMPT")
    elif numbers1 == numbers2:
        labels.append("SAME_HTTP_OR_TIMEOUT_SIGNATURE_BY_ATTEMPT")

    all_attempts = list(run1.values()) + list(run2.values())
    statuses = [attempt.get("status_code") for attempt in all_attempts]
    if 400 in statuses:
        labels.append("HTTP_400_OBSERVED")
    if 404 in statuses:
        labels.append("HTTP_404_OBSERVED")
    if any(status in (429, 502, 503) for status in statuses):
        labels.append("HTTP_429_502_503_OBSERVED")
    if any(attempt.get("timed_out") is True for attempt in all_attempts):
        labels.append("TIMEOUT_OBSERVED")
    if any(
        attempt.get("status_code") is None and attempt.get("error")
        for attempt in all_attempts
    ):
        labels.append("ERROR_WITHOUT_HTTP_STATUS_OBSERVED")

    return ",".join(labels) if labels else "NO_CLASSIFICATION"


def status_sequence(attempts: dict[int, dict[str, Any]]) -> str:
    return ",".join(
        f"{number}:{'NO_STATUS' if item.get('status_code') is None else item['status_code']}"
        for number, item in sorted(attempts.items())
    ) or "MISSING"


def main() -> int:
    run1 = normalize(load(RUN1))
    run2 = normalize(load(RUN2))
    ids1, ids2 = set(run1), set(run2)
    common = sorted(ids1 & ids2)

    print("=== INPUT INTEGRITY ===")
    print("Run1 SHA256:", sha256(RUN1))
    print("Run2 SHA256:", sha256(RUN2))
    print("\n=== MODEL AND STATUS COUNTS ===")
    print("Run1 models:", len(run1), "| Run2 models:", len(run2))
    print("Common models:", len(common))
    print("Only Run1:", sorted(ids1 - ids2))
    print("Only Run2:", sorted(ids2 - ids1))
    print("Run1 HTTP status counts:", dict(status_counts(run1)))
    print("Run2 HTTP status counts:", dict(status_counts(run2)))

    same_status = 0
    changed_status = 0
    changed_attempt_set = 0

    print("\n=== ATTEMPT-ALIGNED COMPARISON ===")
    print(
        "MODEL | RUN1 ATTEMPTS | RUN2 ATTEMPTS | RUN1 MEDIAN MS | "
        "RUN2 MEDIAN MS | CLASSIFICATION"
    )
    for model in sorted(ids1 | ids2):
        attempts1 = run1.get(model, {})
        attempts2 = run2.get(model, {})
        if set(attempts1) != set(attempts2):
            changed_attempt_set += 1
        elif any(
            attempts1[n].get("status_code") != attempts2[n].get("status_code")
            or attempts1[n].get("timed_out") != attempts2[n].get("timed_out")
            for n in attempts1
        ):
            changed_status += 1
        else:
            same_status += 1

        print(
            f"{model} | {status_sequence(attempts1)} | {status_sequence(attempts2)} | "
            f"{median_latency(attempts1)} | {median_latency(attempts2)} | "
            f"{classify(attempts1, attempts2)}"
        )

    expected_attempts = {1, 2, 3}
    checks = [
        ("Run1 = 87 models", len(run1) == 87),
        ("Run2 = 87 models", len(run2) == 87),
        ("same model set", ids1 == ids2),
        (
            "Run1 every model has attempts 1,2,3 exactly once",
            all(set(attempts) == expected_attempts for attempts in run1.values()),
        ),
        (
            "Run2 every model has attempts 1,2,3 exactly once",
            all(set(attempts) == expected_attempts for attempts in run2.values()),
        ),
    ]
    print("\n=== SUMMARY ===")
    print("Models with same attempt set and HTTP/timeout signature:", same_status)
    print("Models with changed HTTP/timeout signature by attempt:", changed_status)
    print("Models with changed attempt set:", changed_attempt_set)
    print("\n=== STRUCTURAL CHECKS ===")
    for name, passed in checks:
        print(("PASS " if passed else "FAIL ") + name)
    print("\nSTRUCTURAL_STATE:", "VERIFIED" if all(ok for _, ok in checks) else "HOLD")
    print("AVAILABILITY_REPEATABILITY:", "PARTIAL" if changed_status else "NOT_ASSESSED")
    print("CAUSALITY: UNKNOWN")
    print("MODEL_QUALITY: NOT_EVALUATED")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
