from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from jamp.api import create_app


def _executor(model, payload):
    return {
        "provider": "openrouter",
        "model": model,
        "provider_response_id": "e4-integration-generation",
        "provider_model_id": "provider/e4-test",
        "content": "SBER достиг 5000₽",
    }


def _client(monkeypatch, executor=_executor):
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "integration-test-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda output: ("VERIFIED", {"reason": "TEST_E2_VERIFIED"}),
    )
    return app_module, TestClient(create_app(executor=executor))


def test_text_fallback_extracts_adapts_routes_moex_and_aggregates(monkeypatch):
    app_module, client = _client(monkeypatch)
    calls = {"extract": 0, "adapter": 0, "moex": []}
    real_extract = app_module.extract_claims
    real_adapter = app_module.to_verdict_claim

    def extract_spy(text):
        calls["extract"] += 1
        return real_extract(text)

    def adapter_spy(extracted, trace_id):
        calls["adapter"] += 1
        return real_adapter(extracted, trace_id)

    def moex_spy(ticker, claim_type, claimed_value):
        calls["moex"].append((ticker, claim_type, claimed_value))
        return "E4_VERIFIED", {"ticker": ticker, "observed_last": 5000.0}

    monkeypatch.setattr(app_module, "extract_claims", extract_spy)
    monkeypatch.setattr(app_module, "to_verdict_claim", adapter_spy)
    monkeypatch.setattr(app_module, "verify_claim_with_moex", moex_spy)

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Проверь цену."},
    )

    assert response.status_code == 200
    body = response.json()
    assert calls["extract"] == 1
    assert calls["adapter"] == 1
    assert calls["moex"] == [("SBER", "price", 5000.0)]
    assert body["aggregate_status"] == "VERIFIED"
    assert body["claims"][0]["status"] == "VERIFIED"
    assert body["claims"][0]["claim_id"].startswith(body["trace_id"] + "_")
    assert body["verdict"]["trace_id"] == body["trace_id"]


def test_entity_existence_is_inconclusive_without_moex(monkeypatch):
    app_module, client = _client(
        monkeypatch,
        executor=lambda model, payload: {
            **_executor(model, payload),
            "content": "FakeTech объявила IPO",
        },
    )
    monkeypatch.setattr(
        app_module,
        "verify_claim_with_moex",
        lambda *args: (_ for _ in ()).throw(AssertionError("MOEX must not be called")),
    )

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Проверь факт."},
    )

    assert response.status_code == 200
    claim = response.json()["claims"][0]
    assert claim["type"] == "entity_existence"
    assert claim["status"] == "INCONCLUSIVE"
    assert claim["source"] is None


def test_unknown_unit_is_inconclusive_without_external_api(monkeypatch):
    app_module, client = _client(
        monkeypatch,
        executor=lambda model, payload: {
            **_executor(model, payload),
            "content": "Цена SBER составляет 5000",
        },
    )

    def unexpected_api(*args, **kwargs):
        raise AssertionError("External E4 APIs must not be called")

    monkeypatch.setattr(app_module, "verify_claim_with_moex", unexpected_api)
    monkeypatch.setattr(app_module, "verify_claim_with_coingecko", unexpected_api)

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Проверь цену."},
    )

    assert response.status_code == 200
    claim = response.json()["claims"][0]
    assert claim["unit"] == "UNKNOWN"
    assert claim["status"] == "INCONCLUSIVE"
    assert claim["source"] is None


def test_structured_e4_claim_has_priority_over_extractor(monkeypatch):
    app_module, client = _client(monkeypatch)
    monkeypatch.setattr(
        app_module,
        "extract_claims",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Structured e4_claim must take priority")
        ),
    )
    moex_calls = []
    monkeypatch.setattr(
        app_module,
        "verify_claim_with_moex",
        lambda ticker, claim_type, value: (
            moex_calls.append((ticker, claim_type, value))
            or ("E4_VERIFIED", {"ticker": ticker, "observed_last": value})
        ),
    )

    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "Проверь цену SBER.",
            "e4_claim": {
                "ticker": "SBER",
                "claim_type": "price",
                "claimed_value": 5000,
                "unit": "RUB",
            },
        },
    )

    assert response.status_code == 200
    assert moex_calls == [("SBER", "price", 5000)]
    assert response.json()["claims"][0]["status"] == "VERIFIED"
