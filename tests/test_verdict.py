from __future__ import annotations

from fastapi.testclient import TestClient

from jamp.api import create_app
from jamp.runtime.verdict import JampVerdict


def test_verdict_signature_is_deterministic_and_detects_tampering():
    verdict = JampVerdict(
        trace_id="trace_12345678",
        status="VERIFIED",
        provider_model_id="provider/model-a",
        evidence_hash="sha256:abc123",
        timestamp=1792939980.25,
    )
    signed = verdict.sign("test-signing-key")

    assert signed.signature is not None
    assert signed.verify("test-signing-key")
    assert not signed.verify("wrong-key")
    assert not JampVerdict(
        trace_id="trace_87654321",
        status=signed.status,
        provider_model_id=signed.provider_model_id,
        evidence_hash=signed.evidence_hash,
        timestamp=signed.timestamp,
        signature=signed.signature,
    ).verify("test-signing-key")


def test_execute_emits_verdict_and_verify_endpoint_rejects_tampered_trace(monkeypatch):
    import importlib

    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module, "verify_generation", lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"})
    )

    def executor(model, payload):
        return {
            "provider": "openrouter",
            "model": model,
            "provider_response_id": "generation-1",
            "provider_model_id": "provider/model-a",
            "content": "verified result",
        }

    client = TestClient(create_app(executor=executor))
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Say hello"},
    )

    assert response.status_code == 200
    body = response.json()
    verdict = body["verdict"]
    assert verdict["status"] == "VERIFIED"
    assert verdict["trace_id"] == body["trace_id"]
    assert verdict["evidence_hash"].startswith("sha256:")
    assert client.post("/v1/verify-verdict", json=verdict).json() == {"valid": True}

    tampered = {**verdict, "trace_id": verdict["trace_id"] + "x"}
    assert client.post("/v1/verify-verdict", json=tampered).json() == {"valid": False}


def test_production_without_signing_key_fails_closed(monkeypatch):
    import importlib

    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.delenv("JAMP_SIGNING_KEY", raising=False)
    monkeypatch.setenv("JAMP_ENV", "production")
    monkeypatch.setattr(
        app_module, "verify_generation", lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"})
    )

    client = TestClient(
        create_app(
            executor=lambda model, payload: {
                "provider": "openrouter",
                "model": model,
                "provider_response_id": "generation-2",
                "provider_model_id": "provider/model-a",
                "content": "verified result",
            }
        )
    )
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Say hello"},
    )

    assert response.status_code == 503
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "SIGNING_KEY_NOT_CONFIGURED"
