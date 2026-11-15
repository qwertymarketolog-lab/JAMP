from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jamp.api import create_app

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "docs/experiments/jamp_audit_v1/vertical_experiment_v1.json"


def _executor(model, payload):
    return {
        "provider": "openrouter",
        "model": model,
        "provider_response_id": "vertical-experiment-generation",
        "provider_model_id": "provider/vertical-experiment-fixture",
        "content": payload["prompt"],
    }


def _client(monkeypatch, content, calls):
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "vertical-experiment-test-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda output: ("VERIFIED", {"reason": "MOCK_GENERATION_FIXTURE"}),
    )

    def moex(ticker, claim_type, value):
        calls["moex"].append((ticker, claim_type, value))
        if claim_type != "price":
            return "E4_INCONCLUSIVE", {"reason": "UNSUPPORTED_CLAIM_TYPE"}
        expected = {"SBER": 300.0, "GAZP": 150.0}.get(ticker)
        if expected is None:
            return "E4_INCONCLUSIVE", {"reason": "MOCK_TICKER_NOT_FOUND"}
        if float(value) == expected:
            return "E4_VERIFIED", {
                "ticker": ticker,
                "observed_last": expected,
                "claimed_value": float(value),
                "comparison": "exact",
            }
        return "E4_CONTRADICTED", {
            "ticker": ticker,
            "observed_last": expected,
            "claimed_value": float(value),
            "comparison": "exact",
        }

    def coingecko(coin_id, claim_type, value):
        calls["coingecko"].append((coin_id, claim_type, value))
        if coin_id == "bitcoin" and claim_type == "price" and float(value) == 65000.0:
            return "E4_VERIFIED", {
                "coin_id": coin_id,
                "observed_value": 65000.0,
                "claimed_value": float(value),
                "comparison": "exact",
            }
        return "E4_CONTRADICTED", {"coin_id": coin_id, "claimed_value": value}

    monkeypatch.setattr(app_module, "verify_claim_with_moex", moex)
    monkeypatch.setattr(app_module, "verify_claim_with_coingecko", coingecko)
    executor = lambda model, payload: {**_executor(model, payload), "content": content}
    return TestClient(create_app(executor=executor))


@pytest.fixture(scope="module")
def cases():
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    assert payload["mode"] == "offline_mock_only"
    assert len(payload["cases"]) == 10
    return payload["cases"]


@pytest.mark.parametrize("case_id", [f"C{i}" for i in range(1, 11)])
def test_vertical_experiment_case_matrix(case_id, cases, monkeypatch):
    case = next(item for item in cases if item["id"] == case_id)
    calls = {"moex": [], "coingecko": []}
    client = _client(monkeypatch, case["text"], calls)

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": case["text"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("claims"), list)
    assert body["claims"], f"{case_id}: E4 emitted no claims"

    if case_id == "C5":
        target = next(claim for claim in body["claims"] if claim["type"] == "entity_existence")
    elif case_id == "C7":
        target = next(claim for claim in body["claims"] if claim["type"] == "price")
    else:
        target = next(
            (
                claim for claim in body["claims"]
                if claim.get("type") in {"price", "prediction", "causal"}
            ),
            body["claims"][0],
        )

    assert target["status"] == case["expected_e4"], (
        f"{case_id}: expected {case['expected_e4']}, got {target['status']}; "
        f"claims={body['claims']}"
    )

    if case_id in {"C4", "C5", "C6", "C8", "C9"}:
        assert calls == {"moex": [], "coingecko": []}, (
            f"{case_id}: out-of-scope or incomplete claims must not call providers"
        )
    elif case_id in {"C1", "C2", "C7", "C10"}:
        assert calls["moex"] == [(case["ticker"], "price", case["claimed_value"])]
        assert calls["coingecko"] == []
    elif case_id == "C3":
        assert calls["moex"] == []
        assert calls["coingecko"] == [("bitcoin", "price", 65000)]


def test_experiment_dataset_has_unique_case_ids(cases):
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)) == 10


def test_prediction_and_causal_routing_fails_closed_without_provider_calls(monkeypatch):
    for text in (
        "Завтра SBER будет стоить 1000 RUB",
        "SBER упал из-за отчета на 5% до 290 RUB",
    ):
        calls = {"moex": [], "coingecko": []}
        client = _client(monkeypatch, text, calls)
        response = client.post(
            "/v1/execute",
            json={"intent": "search_and_extraction", "prompt": text},
        )
        assert response.status_code == 200
        assert calls == {"moex": [], "coingecko": []}
        assert any(
            claim["type"] in {"prediction", "causal"} and claim["status"] == "INCONCLUSIVE"
            for claim in response.json()["claims"]
        )
