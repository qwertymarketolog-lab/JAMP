"""Tests for signature re-verification on GET endpoints.

Security regression test: tampered JSONL must return 500, not 200.
"""

import json

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module
from jamp.api.app import create_app

pytestmark = pytest.mark.real_auth

AUTH = {"Authorization": "Bearer test-token"}
SPEC = {"spec_id": "s1", "criteria_id": "c1"}


@pytest.fixture
def client_and_paths(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda _d: ("VERIFIED", {"reason": "INTEGRITY_TEST"}),
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
            "provider_response_id": "integrity",
            "provider_model_id": model,
            "content": '{"result":"integrity"}',
        }

    audit_path = tmp_path / "audit" / "provenance_traces.jsonl"
    app = create_app(executor=_exec, audit_storage_path=audit_path)
    return TestClient(app), audit_path


def _make_jv(client, req="i-1"):
    r = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "test",
            "request_id": req,
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["trace_id"], body["verdict"]


def _make_uv(client, jv):
    r = client.post(
        "/v1/universal-verdict",
        json={"jamp_verdict": jv, **SPEC},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _tamper_jsonl(path, trace_id, mutator):
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("trace_id") == trace_id:
            rec = mutator(rec)
        out.append(json.dumps(rec, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --- GET /v1/jamp-verdict/{trace_id} ---


def test_jv_get_valid(client_and_paths):
    client, _ = client_and_paths
    trace_id, _ = _make_jv(client)
    r = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 200


def test_jv_get_tampered_signature_500(client_and_paths):
    client, audit_path = client_and_paths
    trace_id, _ = _make_jv(client)

    _tamper_jsonl(
        audit_path.parent / "verdicts.jsonl",
        trace_id,
        lambda rec: {**rec, "signature": "deadbeef"},
    )
    r = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 500


def test_jv_get_tampered_payload_500(client_and_paths):
    client, audit_path = client_and_paths
    trace_id, _ = _make_jv(client)

    _tamper_jsonl(
        audit_path.parent / "verdicts.jsonl",
        trace_id,
        lambda rec: {**rec, "aggregate_status": "CONTRADICTED"},
    )
    r = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 500


# --- GET /v1/universal-verdict/{trace_id} ---


def test_uv_get_valid(client_and_paths):
    client, _ = client_and_paths
    trace_id, jv = _make_jv(client)
    _make_uv(client, jv)

    r = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 200


def test_uv_get_tampered_signature_500(client_and_paths):
    client, audit_path = client_and_paths
    trace_id, jv = _make_jv(client)
    _make_uv(client, jv)

    _tamper_jsonl(
        audit_path.parent / "universal_verdicts.jsonl",
        trace_id,
        lambda rec: {**rec, "signature": "deadbeef"},
    )
    r = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 500


def test_uv_get_tampered_verdict_hash_500(client_and_paths):
    client, audit_path = client_and_paths
    trace_id, jv = _make_jv(client)
    _make_uv(client, jv)

    _tamper_jsonl(
        audit_path.parent / "universal_verdicts.jsonl",
        trace_id,
        lambda rec: {**rec, "verdict_hash": "sha256:" + "0" * 64},
    )
    r = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 500
