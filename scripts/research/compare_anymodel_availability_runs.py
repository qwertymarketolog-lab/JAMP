#!/usr/bin/env python3
"""Compare two AnyModel N=3 availability evidence artifacts.

Read-only comparative audit; no API requests and no runtime/Frozen Core changes.
Run 1 and Run 2 have different schemas, so their actual structures are
resolved instead of assuming one common field layout.
"""

from __future__ import annotations

import hashlib
import json
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


def status_signature(attempt: dict[str, Any]) -> tuple[Any, ...]:
    transport = attempt.get("transport", {})
    response = attempt.get("response", {})
    if not isinstance(transport, dict):
        transport = {}
    if not isinstance(response, dict):
        response = {}
    parsed = response.get("parsed_body")
    error_code = None
    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict):
            error_code = error.get("code")
    return (
        transport.get("status_code"),
        transport.get("timed_out"),
        response.get("json_parse_ok"),
        error_code,
    )


def normalize(document: dict[str, Any]) -> dict[str, list[tuple[Any, ...]]]:
    rows = (
        document.get("results")
        if isinstance(document.get("results"), list)
        else document.get("models")
    )
    if not isinstance(rows, list):
        raise RuntimeError(f"Unknown artifact structure: top-level keys={list(document)}")
    normalized: dict[str, list[tuple[Any, ...]]] = {}
    for row in rows:
        model_id = get_model_id(row)
        normalized[model_id] = [status_signature(attempt) for attempt in get_attempts(row)]
    return normalized


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    run1 = normalize(load(RUN1))
    run2 = normalize(load(RUN2))
    ids1, ids2 = set(run1), set(run2)
    common = sorted(ids1 & ids2)
    identical = [model for model in common if run1[model] == run2[model]]
    different = [model for model in common if run1[model] != run2[model]]

    print("=== RUN 1 vs RUN 2 ===")
    print("Run1 SHA256:", sha256(RUN1))
    print("Run2 SHA256:", sha256(RUN2))
    print("\n=== MODELS ===")
    print("Run1:", len(run1))
    print("Run2:", len(run2))
    print("Common:", len(common))
    print("Only Run1:", sorted(ids1 - ids2))
    print("Only Run2:", sorted(ids2 - ids1))
    print("\n=== ATTEMPTS ===")
    print("Run1:", Counter(map(len, run1.values())))
    print("Run2:", Counter(map(len, run2.values())))
    print("\n=== REPEATABILITY ===")
    print("Identical:", len(identical))
    print("Different:", len(different))
    print("\n=== DIFFERENCES ===")
    for model in different:
        print("\nMODEL:", model)
        print("Run1:", run1[model])
        print("Run2:", run2[model])

    checks = [
        ("Run1 = 87 models", len(run1) == 87),
        ("Run2 = 87 models", len(run2) == 87),
        ("same model set", ids1 == ids2),
        ("Run1 every model = 3 attempts", all(len(v) == 3 for v in run1.values())),
        ("Run2 every model = 3 attempts", all(len(v) == 3 for v in run2.values())),
    ]
    print("\n=== STRUCTURAL CHECKS ===")
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    print("\nSTATE:", "VERIFIED" if all(ok for _, ok in checks) else "HOLD")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
