"""Tests for GET /v1/jamp-verdict/{trace_id}."""

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module
from jamp.api.app import create_app

pytestmark = pytest.mark.real_auth

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda _d: ("VERIFIED", {"reason": "JV_GET_TEST"}),
    )
    monkeypatch.setattr(
        auth_module,
        "_lookup_by_hash",
        lambda _h: ("test-org", "test", False),
    )

    def _exec(model, payload):
        return {
            "provider": "stub",
            "model": model,
            "provider_response_id": "jv-get",
            "provider_model_id": model,
            "content": '{"result":"jv-get"}',
        }

    app = create_app(
        executor=_exec,
        audit_storage_path=tmp_path / "audit" / "provenance_traces.jsonl",
    )
    return TestClient(app)


def test_no_auth_401(client):
    assert client.get("/v1/jamp-verdict/some-id").status_code == 401


def test_unknown_trace_404(client):
    response = client.get("/v1/jamp-verdict/does-not-exist", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["detail"] == "Verdict not found for trace_id"


def test_execute_then_get_returns_same_verdict(client):
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "test", "request_id": "jv-1"},
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    original = body["verdict"]
    trace_id = body["trace_id"]

    get_response = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert get_response.status_code == 200, get_response.text
    stored = get_response.json()
    assert stored == original
    assert stored["trace_id"] == trace_id
    assert stored["signature"] == original["signature"]
    assert stored["aggregate_status"] == original["aggregate_status"]


def test_stored_verdict_verifies_via_verify_endpoint(client):
    execute_response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "test", "request_id": "jv-2"},
        headers=AUTH,
    )
    assert execute_response.status_code == 200, execute_response.text
    trace_id = execute_response.json()["trace_id"]

    get_response = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert get_response.status_code == 200, get_response.text
    stored = get_response.json()

    verify_response = client.post("/v1/verify-verdict", json=stored, headers=AUTH)
    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["valid"] is True
