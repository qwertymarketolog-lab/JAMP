#!/usr/bin/env python3
"""jamp-87-runtime-v1: canonical 87-model runtime contract.

The canonical manifest is the sole cohort source.  Live /v1/models is never
used to construct the execution cohort.  Existing anymodel_audit.run_model
probe semantics are reused unchanged.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import sys
from collections import Counter
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "artifacts/research/jamp_canonical_manifest_87_36_17_v1.json"
DEFAULT_OUTPUT = ROOT / "artifacts/research/anymodel_87_runtime_v1.json"
EXPECTED = 87
CHECK_IDS = [f"R{i:02d}" for i in range(1, 31)]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_manifest(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    rows = manifest.get("manifest")
    if not isinstance(rows, list):
        raise ValueError("manifest.manifest must be a list")
    if len(rows) != EXPECTED:
        raise ValueError(f"expected {EXPECTED} manifest rows, observed {len(rows)}")
    ordinals = [row.get("ordinal") for row in rows if isinstance(row, dict)]
    model_ids = [row.get("model_id") for row in rows if isinstance(row, dict)]
    if ordinals != list(range(1, EXPECTED + 1)):
        raise ValueError("manifest ordinals are not exactly 1..87")
    if len(model_ids) != EXPECTED or any(not isinstance(x, str) or not x for x in model_ids):
        raise ValueError("manifest model_id set is invalid")
    if len(set(model_ids)) != EXPECTED:
        raise ValueError("manifest contains duplicate model_id values")
    return manifest, sha256_bytes(raw)


def load_audit_module():
    path = ROOT / "anymodel_audit.py"
    spec = importlib.util.spec_from_file_location("jamp_anymodel_audit", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load anymodel_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_model_rows(manifest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": row["model_id"]} for row in manifest_rows]


def aggregate(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter[str]] = {cid: Counter() for cid in CHECK_IDS}
    for record in records:
        checks = record.get("checks")
        if not isinstance(checks, list):
            raise ValueError(f"missing checks for {record.get('model_id')}")
        by_check = {
            check.get("check_id"): check for check in checks if isinstance(check, dict)
        }
        if set(by_check) != set(CHECK_IDS):
            raise ValueError(f"check coverage mismatch for {record.get('model_id')}")
        for cid in CHECK_IDS:
            status = by_check[cid].get("status")
            if status not in {"VERIFIED", "CONTRADICTED", "INCONCLUSIVE"}:
                raise ValueError(
                    f"invalid status {status!r} for {record.get('model_id')} {cid}"
                )
            counts[cid][status] += 1
    out = {}
    for cid in CHECK_IDS:
        item = dict(counts[cid])
        item["total"] = sum(counts[cid].values())
        if item["total"] != EXPECTED:
            raise ValueError(f"{cid} aggregate total != {EXPECTED}")
        out[cid] = item
    return out


def cohort_gate(canonical_ids: list[str], records: list[dict[str, Any]]) -> dict[str, Any]:
    executed_ids = [r.get("model_id") for r in records]
    counts = Counter(executed_ids)
    missing = [mid for mid in canonical_ids if counts[mid] == 0]
    duplicate = [mid for mid in canonical_ids if counts[mid] > 1]
    unknown = [mid for mid in counts if mid not in set(canonical_ids)]
    executed = len(records)
    passed = (
        EXPECTED == EXPECTED
        and executed == EXPECTED
        and not missing
        and not duplicate
        and not unknown
        and set(executed_ids) == set(canonical_ids)
    )
    return {
        "expected": EXPECTED,
        "executed": executed,
        "missing": missing,
        "duplicate": duplicate,
        "unknown": unknown,
        "gate": "PASS" if passed else "FAIL",
    }


def deterministic_artifact(
    manifest_sha: str, manifest_rows: list[dict[str, Any]], records: list[dict[str, Any]]
) -> dict[str, Any]:
    gate = cohort_gate([r["model_id"] for r in manifest_rows], records)
    if gate["gate"] != "PASS":
        raise RuntimeError(json.dumps({"cohort_gate": gate}, sort_keys=True))
    return {
        "contract_version": "jamp-87-runtime-v1",
        "canonical_manifest_sha256": manifest_sha,
        "expected": EXPECTED,
        "executed": len(records),
        "missing": gate["missing"],
        "duplicate": gate["duplicate"],
        "unknown": gate["unknown"],
        "cohort_gate": gate["gate"],
        "models": records,
        "aggregate": aggregate(records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    manifest, manifest_sha = load_manifest(args.manifest)
    module = load_audit_module()
    availability = module.load_available(module.DEFAULT_AVAILABILITY)
    headers = {
        "Authorization": f"Bearer {__import__('os').environ.get('ANYMODEL_API_KEY', '')}"
    }
    if headers["Authorization"] == "Bearer ":
        raise SystemExit("ANYMODEL_API_KEY is required")

    rows = build_model_rows(manifest["manifest"])
    records = []
    started = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    for ordinal, row in enumerate(rows, 1):
        record = module.run_model(headers, row, availability)
        record["ordinal"] = ordinal
        record["execution_id"] = digest(
            {"ordinal": ordinal, "model_id": row["id"], "started": started}
        )
        records.append(record)

    artifact = deterministic_artifact(manifest_sha, manifest["manifest"], records)
    artifact["started_at"] = started
    artifact["finished_at"] = dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"WROTE {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
