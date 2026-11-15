from __future__ import annotations

import json
from pathlib import Path

from scripts.research.run_vertical_experiment import run_vertical_experiment

DATASET = (
    Path(__file__).resolve().parents[2]
    / "docs/experiments/jamp_audit_v1/vertical_experiment_v1.json"
)


def test_vertical_experiment_v1_runs_all_cases_through_e4(tmp_path):
    output = tmp_path / "vertical_experiment_results.json"
    result = run_vertical_experiment(DATASET, output)

    assert result["provider_mode"] == "MOCK_ONLY"
    assert result["external_provider_calls"] == 0
    assert result["case_count"] == 10
    assert result["extraction_failures"] == []
    assert result["verdict_failures"] == []
    assert output.is_file()

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == result
    assert {item["id"] for item in result["results"]} == {
        f"c{number}" for number in range(1, 11)
    }


def test_prediction_and_causal_claims_never_call_external_verifiers(tmp_path):
    result = run_vertical_experiment(DATASET, tmp_path / "results.json")
    by_id = {item["id"]: item for item in result["results"]}

    for case_id in ("c7", "c8"):
        assert by_id[case_id]["e4_status"] == "INCONCLUSIVE"
        assert by_id[case_id]["reason"] == "NOT_A_PRICE_CLAIM"
        assert by_id[case_id]["mock_calls"] == []


def test_historical_price_is_inconclusive_without_current_price_lookup(tmp_path):
    result = run_vertical_experiment(DATASET, tmp_path / "results.json")
    case = next(item for item in result["results"] if item["id"] == "c10")

    assert case["extracted_claim"] == {
        "type": "price",
        "value": 300.0,
        "unit": "RUB",
        "ticker": "SBER",
    }
    assert case["e4_status"] == "INCONCLUSIVE"
    assert case["reason"] == "HISTORICAL_CLAIM_OUTSIDE_E4_SCOPE"
    assert case["mock_calls"] == []


def test_bounded_mock_catalog_does_not_claim_real_market_absence(tmp_path):
    result = run_vertical_experiment(DATASET, tmp_path / "results.json")
    case = next(item for item in result["results"] if item["id"] == "c9")

    assert case["e4_status"] == "OUT_OF_SCOPE"
    assert case["mock_calls"] == [
        {
            "provider": "MOEX",
            "ticker": "GAZP",
            "claim_type": "price",
            "claimed_value": 150.0,
        }
    ]
