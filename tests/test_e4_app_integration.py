from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from jamp.api import create_app


def _verified_executor(model, payload):
    return {
        "provider": "openrouter",
        "model": model,
        "provider_response_id": "generation-e4-test",
        "provider_model_id": "provider/model-a",
        "content": "Analysis returned for the supplied prompt.",
    }


def test_ipo_claim_outside_moex_scope_is_partial_not_global_refusal(monkeypatch):
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module, "verify_generation", lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"})
    )

    client = TestClient(create_app(executor=_verified_executor))
    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "VK Tech готовится к IPO. Это перспективный актив.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "EXECUTE"
    assert body["evidence_status"] == "VERIFIED"
    assert body["aggregate_status"] == "PARTIAL"
    assert any(claim["type"] == "ipo_event" for claim in body["claims"])
    assert body["critical_unverified"] == []
    assert body["verdict"]["model_verification"] == "VERIFIED"
    assert body["verdict"]["aggregate_status"] == "PARTIAL"


def test_direct_moex_contradiction_refuses_and_preserves_e4_details(monkeypatch):
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module, "verify_generation", lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"})
    )
    monkeypatch.setattr(
        app_module,
        "verify_claim_with_moex",
        lambda ticker, claim_type, claimed_value: (
            "E4_CONTRADICTED",
            {"ticker": ticker, "observed_last": 292.32, "claimed_value": claimed_value},
        ),
    )

    client = TestClient(create_app(executor=_verified_executor))
    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "Проверь цену SBER",
            "e4_claim": {"ticker": "SBER", "claim_type": "price", "claimed_value": 5000},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REFUSE"
    assert body["evidence_status"] == "CONTRADICTED"
    assert body["e4_details"]["e4_status"] == "E4_CONTRADICTED"
    assert body["e4_details"]["observed_last"] == 292.32
    assert "verdict" not in body
