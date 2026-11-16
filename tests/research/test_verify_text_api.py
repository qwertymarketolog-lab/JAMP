from __future__ import annotations

import base64
import hashlib
import importlib

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth
from jamp.api import create_app

VALID_TOKEN = "jamp_sk_verify_text_test"  # noqa: S105


def _raw_evidence(source: str = "https://provider.example/data") -> list[dict]:
    body = b'{"observed":300.0}'
    return [{
        "source": source,
        "url": source,
        "status_code": 200,
        "body_complete": True,
        "raw_body_base64": base64.b64encode(body).decode("ascii"),
        "sha256_body": hashlib.sha256(body).hexdigest(),
    }]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "verify-text-test-secret")
    monkeypatch.setattr(
        auth,
        "_lookup_by_hash",
        lambda _digest: ("org-42", "test-org", False),
    )
    return TestClient(create_app(), raise_server_exceptions=False)


def _post(client: TestClient, text: str):
    return client.post(
        "/v1/verify_text",
        json={"text": text},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )


def test_multi_claim_returns_two_independent_results(client, monkeypatch):
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setattr(
        app_module,
        "verify_claim_with_moex",
        lambda *_args, **_kwargs: (
            app_module.E4_VERIFIED,
            {"observed_last": 300.0, "raw_evidence": _raw_evidence("https://moex.example/sber")},
        ),
    )
    monkeypatch.setattr(
        app_module,
        "verify_claim_with_coingecko",
        lambda *_args, **_kwargs: (
            app_module.E4_VERIFIED,
            {"observed_value": 60000.0, "raw_evidence": _raw_evidence("https://cg.example/btc")},
        ),
    )

    response = _post(
        client,
        "Цена SBER составляет 300 RUB. Цена BTC составляет 60000 USD.",
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETE_VERIFICATION"
    assert len(body["claims"]) == 2
    assert [item["verdict"] for item in body["claims"]] == ["VERIFIED", "VERIFIED"]
    assert body["system_warnings"]


def test_no_claims_returns_no_claims_and_warning(client):
    response = _post(client, "Hello, how are you?")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NO_CLAIMS"
    assert body["claims"] == []
    assert body["system_warnings"]
    assert "does not mean" in body["system_warnings"][0]


def test_provider_failure_does_not_erase_other_claim_result(client, monkeypatch):
    app_module = importlib.import_module("jamp.api.app")

    monkeypatch.setattr(
        app_module,
        "verify_claim_with_moex",
        lambda *_args, **_kwargs: (
            app_module.E4_VERIFIED,
            {"observed_last": 300.0, "raw_evidence": _raw_evidence("https://moex.example/sber")},
        ),
    )

    class ProviderHTTPError(RuntimeError):
        code = 500

    def fail_coingecko(*_args, **_kwargs):
        raise ProviderHTTPError("upstream failure")

    monkeypatch.setattr(app_module, "verify_claim_with_coingecko", fail_coingecko)

    response = _post(
        client,
        "Цена SBER составляет 300 RUB. Цена BTC составляет 60000 USD.",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PARTIAL_VERIFICATION"
    assert [item["verdict"] for item in body["claims"]] == ["VERIFIED", "INCONCLUSIVE"]
    assert body["claims"][1]["reason"] == "PROVIDER_ERROR"
    assert body["provider_errors"][0]["provider"] == "CoinGecko"
    assert body["provider_errors"][0]["status"] == "HTTP_500"


def test_evidence_contains_capture_timestamp_and_raw_hash(client, monkeypatch):
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setattr(
        app_module,
        "verify_claim_with_moex",
        lambda *_args, **_kwargs: (
            app_module.E4_VERIFIED,
            {"observed_last": 300.0, "raw_evidence": _raw_evidence("https://moex.example/sber")},
        ),
    )

    response = _post(client, "Цена SBER составляет 300 RUB.")

    assert response.status_code == 200
    evidence = response.json()["claims"][0]["evidence"][0]
    assert evidence["timestamp_utc"].endswith("Z")
    assert evidence["timestamp_kind"] == "JAMP_CAPTURE_TIME"
    assert evidence["age_seconds"] >= 0
    assert evidence["raw_sha256"] == hashlib.sha256(b'{"observed":300.0}').hexdigest()
