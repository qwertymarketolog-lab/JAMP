from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "experiments" / "stock_audit" / "test_cases"


def test_stock_audit_v2_has_exactly_24_ordered_cases() -> None:
    files = sorted(CASES.glob("T*.json"))
    assert len(files) == 24
    assert [path.stem for path in files] == [f"T{i:02d}" for i in range(1, 25)]


def test_stock_audit_v2_case_contract_and_expected_behaviors() -> None:
    for index, path in enumerate(sorted(CASES.glob("T*.json")), start=1):
        case = json.loads(path.read_text(encoding="utf-8"))
        assert case["id"] == f"T{index:02d}"
        assert isinstance(case["text"], str) and case["text"].strip()
        assert isinstance(case["note"], str) and case["note"].strip()
        assert case["expected_behavior"] in {
            "VERIFIED",
            "PARTIAL",
            "REFUSE",
            "INCONCLUSIVE",
            "INCONCLUSIVE/REFUSE",
        }
    assert (
        json.loads((CASES / "T07.json").read_text(encoding="utf-8"))["expected_behavior"]
        == "PARTIAL"
    )
    assert (
        json.loads((CASES / "T23.json").read_text(encoding="utf-8"))["expected_behavior"]
        == "REFUSE"
    )
