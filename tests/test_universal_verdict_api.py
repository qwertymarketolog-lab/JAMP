"""Tests for POST /v1/universal-verdict (Universal Verdict v0 envelope).

Marked real_auth: bypass from root conftest must NOT apply, otherwise
require_api_key is stubbed and 401 cannot be tested.
"""
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
        lambda _d: ("VERIFIED", {"reason": "UV_TEST_FIXTURE"}),
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
            "provider_response_id": "uv-test",
            "provider_model_id": model,
            "content": '{"result":"uv-fixture"}',
        }

    app = create_app(executor=_exec, audit_storage_path=tmp_path / "audit.jsonl")
    return TestClient(app)


@pytest.fixture
def valid_jv(client):
    r = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "test", "request_id": "uv-test"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    return r.json()["verdict"]


def test_no_auth_401(client):
    assert client.post("/v1/universal-verdict", json={}).status_code == 401


def test_missing_spec_or_criteria_400(client, valid_jv):
    r = client.post("/v1/universal-verdict", json={"jamp_verdict": valid_jv}, headers=AUTH)
    assert r.status_code == 400
    assert "spec_id" in r.json()["detail"]


def test_bad_jamp_signature_400(client, valid_jv):
    tampered = dict(valid_jv, signature="deadbeef")
    r = client.post(
        "/v1/universal-verdict",
        json={
            "jamp_verdict": tampered,
            "spec_id": "php2shell-remediation-v1",
            "criteria_id": "jamp-patch-verification-v0",
        },
        headers=AUTH,
    )
    assert r.status_code == 400
    assert "signature" in r.json()["detail"].lower()


def test_valid_returns_hash_and_signature(client, valid_jv):
    r = client.post(
        "/v1/universal-verdict",
        json={
            "jamp_verdict": valid_jv,
            "spec_id": "php2shell-remediation-v1",
            "criteria_id": "jamp-patch-verification-v0",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict_hash"].startswith("sha256:")
    assert isinstance(body["signature"], str) and len(body["signature"]) > 0
    assert body["semantics"].startswith("spec_hash/criteria_hash")
    uv = body["universal_verdict"]
    assert uv["verifier"]["reproducible"] is False
    assert uv["evidence_refs"] == []
    assert uv["classification"]["label"] == uv["verdict"]["result"]
