"""Integration contract for the B2B Trust Layer verdict API."""

from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

from jamp.api import create_app


def test_execute_verdict_can_be_verified_and_tampering_is_rejected(monkeypatch):
    """E2 VERIFIED + E3 QUALIFIED yields a signed verdict verifiable over HTTP."""
    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "stage7-test-signing-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"}),
    )
    monkeypatch.setattr(
        app_module,
        "evaluate_model_qualification",
        lambda model_id, task_profile: "QUALIFIED",
    )

    def executor(model, payload):
        return {
            "provider": "openrouter",
            "model": model,
            "provider_response_id": "stage7-generation-1",
            "provider_model_id": "fixture/stage7-model",
            "content": "B2B contract integration test",
        }

    client = TestClient(create_app(executor=executor))
    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "Return a deterministic integration-test response",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "EXECUTE"
    assert body["evidence_status"] == "VERIFIED"
    assert body["qualification"] == "QUALIFIED"

    verdict = body["verdict"]
    assert verdict["status"] == "VERIFIED"
    assert verdict["trace_id"] == body["trace_id"]
    assert verdict["evidence_hash"].startswith("sha256:")
    assert isinstance(verdict["signature"], str) and verdict["signature"]

    verified = client.post("/v1/verify-verdict", json=verdict)
    assert verified.status_code == 200
    assert verified.json() == {"valid": True}

    tampered = dict(verdict)
    signature = tampered["signature"]
    replacement = "0" if signature[0] != "0" else "1"
    tampered["signature"] = replacement + signature[1:]

    rejected = client.post("/v1/verify-verdict", json=tampered)
    assert rejected.status_code == 200
    assert rejected.json() == {"valid": False}
