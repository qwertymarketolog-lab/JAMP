"""Contract tests for jamp-87-runtime-v1 without network execution."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
import audit_87_runtime as harness  # noqa: E402


def test_canonical_manifest_is_87_and_ordered():
    manifest, sha = harness.load_manifest(harness.DEFAULT_MANIFEST)
    assert sha
    rows = manifest["manifest"]
    assert len(rows) == 87
    assert [r["ordinal"] for r in rows] == list(range(1, 88))
    assert len({r["model_id"] for r in rows}) == 87


def test_cohort_gate_requires_exact_87():
    ids = [f"m{i}" for i in range(1, 88)]
    records = [{"model_id": mid, "checks": []} for mid in ids]
    gate = harness.cohort_gate(ids, records)
    assert gate["gate"] == "PASS"
    assert gate["expected"] == gate["executed"] == 87
    assert gate["missing"] == gate["duplicate"] == gate["unknown"] == []


def test_cohort_gate_rejects_duplicate_and_missing():
    ids = [f"m{i}" for i in range(1, 88)]
    records = [{"model_id": mid, "checks": []} for mid in ids[:-1]]
    records.append({"model_id": ids[0], "checks": []})
    gate = harness.cohort_gate(ids, records)
    assert gate["gate"] == "FAIL"
    assert gate["missing"] == [ids[-1]]
    assert gate["duplicate"] == [ids[0]]


def test_aggregate_requires_30_checks_per_model():
    records = []
    for i in range(87):
        records.append(
            {
                "model_id": f"m{i}",
                "checks": [
                    {"check_id": cid, "status": "INCONCLUSIVE"} for cid in harness.CHECK_IDS
                ],
            }
        )
    aggregate = harness.aggregate(records)
    assert len(aggregate) == 30
    assert all(v["total"] == 87 for v in aggregate.values())
    assert all(v["INCONCLUSIVE"] == 87 for v in aggregate.values())
