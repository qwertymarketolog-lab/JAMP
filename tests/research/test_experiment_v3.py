from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.request
from types import SimpleNamespace

from fastapi.testclient import TestClient

os.environ.setdefault("JAMP_ENV", "test")
os.environ.setdefault("JAMP_SIGNING_KEY", "experiment-v3-test-key")

from jamp.api import create_app
from jamp.api.auth import require_api_key

MOEX_SECURITIES = json.dumps({
    "securities": {"columns": ["secid", "shortname"], "data": [["SBER", "Sberbank"]]}
}, separators=(",", ":")).encode()
MOEX_MARKETDATA = json.dumps({
    "marketdata": {
        "columns": ["SECID", "LAST", "BOARDID", "TRADEDATE"],
        "data": [["SBER", 299.26, "TQBR", "2026-11-15"]],
    }
}, separators=(",", ":")).encode()
COINGECKO_PRICE = b'{"bitcoin":{"usd":64754.0}}'


class FakeResponse:
    status = 200

    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size: int = -1) -> bytes:
        return self.body


def _client():
    app = create_app()
    app.dependency_overrides[require_api_key] = lambda: SimpleNamespace(org_id="offline-test")
    return TestClient(app)


def _mock_transport(monkeypatch):
    calls = []

    def open_request(request, timeout=5):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        calls.append(url)
        if "iss.moex.com/iss/securities.json" in url:
            return FakeResponse(MOEX_SECURITIES)
        if "iss.moex.com/iss/engines/stock/markets/shares/securities/SBER.json" in url:
            return FakeResponse(MOEX_MARKETDATA)
        if "api.coingecko.com/api/v3/simple/price" in url and "ids=bitcoin" in url:
            return FakeResponse(COINGECKO_PRICE)
        raise AssertionError(f"unexpected HTTP request: {url}; timeout={timeout}")

    monkeypatch.setattr(urllib.request, "urlopen", open_request)
    return calls


def _assert_raw_evidence(body, expected_bodies):
    evidence = body["raw_evidence"]
    assert len(evidence) == len(expected_bodies)
    for item, expected in zip(evidence, expected_bodies, strict=True):
        raw = base64.b64decode(item["raw_body_base64"], validate=True)
        assert raw == expected
        assert item["status_code"] == 200
        assert item["body_complete"] is True
        assert item["sha256_body"] == hashlib.sha256(raw).hexdigest()


def test_exact_match_is_verified_and_raw_is_same_provider_response(monkeypatch):
    calls = _mock_transport(monkeypatch)
    response = _client().post(
        "/v1/verify_claim",
        json={"text": "Цена SBER 299.26 RUB", "tolerance_pct": 1.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "VERIFIED"
    assert body["verification_mode"] == "DIRECT_E4_NO_E2"
    assert body["tolerance_pct"] == 1.0
    assert body["extracted_claim"]["unit"] == "RUB"
    _assert_raw_evidence(body, [MOEX_SECURITIES, MOEX_MARKETDATA])
    assert len(calls) == 2


def test_strong_divergence_is_contradicted_with_same_raw_response(monkeypatch):
    _mock_transport(monkeypatch)
    response = _client().post(
        "/v1/verify_claim",
        json={"text": "Цена SBER 5000 RUB", "tolerance_pct": 1.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "CONTRADICTED"
    _assert_raw_evidence(body, [MOEX_SECURITIES, MOEX_MARKETDATA])


def test_missing_currency_is_inconclusive_and_does_not_call_provider(monkeypatch):
    calls = _mock_transport(monkeypatch)
    response = _client().post(
        "/v1/verify_claim",
        json={"text": "Цена SBER 299.26", "tolerance_pct": 1.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "INCONCLUSIVE"
    assert body["reason"] == "MISSING_TICKER_VALUE_OR_CURRENCY"
    assert body["raw_evidence"] == []
    assert calls == []


def test_coin_gecko_path_passes_one_percent_and_captures_raw(monkeypatch):
    calls = _mock_transport(monkeypatch)
    response = _client().post(
        "/v1/verify_claim",
        json={"text": "Цена BTC 65000 USD", "tolerance_pct": 1.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "VERIFIED"
    assert body["details"]["threshold_pct"] == 1.0
    _assert_raw_evidence(body, [COINGECKO_PRICE])
    assert len(calls) == 1


def test_endpoint_rejects_invalid_tolerance_and_extra_fields():
    client = _client()
    invalid = client.post(
        "/v1/verify_claim",
        json={"text": "Цена SBER 299.26 RUB", "tolerance_pct": 100},
    )
    extra = client.post(
        "/v1/verify_claim",
        json={"text": "Цена SBER 299.26 RUB", "unexpected": True},
    )
    assert invalid.status_code == 422
    assert extra.status_code == 422


def test_old_provider_calls_remain_compatible_without_raw_capture(monkeypatch):
    _mock_transport(monkeypatch)
    from jamp.provider.moex_verify import verify_claim_with_moex

    status, details = verify_claim_with_moex("SBER", "price", 299.26, price_tolerance=0.01)
    assert status == "E4_VERIFIED"
    assert "raw_evidence" not in details
