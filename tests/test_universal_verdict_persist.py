"""Tests for stateful POST + GET /v1/universal-verdict/{trace_id}."""
import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module
from jamp.api.app import create_app
from jamp.runtime.persistence import AuditPersistence

pytestmark = pytest.mark.real_auth

AUTH = {"Authorization": "Bearer test-token"}
SPEC = {"spec_id": "php2shell-remediation-v1", "criteria_id": "jamp-patch-verification-v0"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda _d: ("VERIFIED", {"reason": "UV_PERSIST_TEST"}),
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
            "provider_response_id": "uv-persist",
            "provider_model_id": model,
            "content": '{"result":"uv-persist"}',
        }

    audit_path = tmp_path / "audit" / "provenance_traces.jsonl"
    app = create_app(executor=_exec, audit_storage_path=audit_path)
    return TestClient(app)


@pytest.fixture
def trace_and_verdict(client):
    r = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "test",
            "request_id": "uvp-1",
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["trace_id"], body["verdict"]


def _post_uv(client, jv, spec=SPEC):
    return client.post(
        "/v1/universal-verdict",
        json={"jamp_verdict": jv, **spec},
        headers=AUTH,
    )


def test_get_without_auth_401(client):
    assert client.get("/v1/universal-verdict/any").status_code == 401


def test_get_unknown_trace_404(client):
    r = client.get("/v1/universal-verdict/does-not-exist", headers=AUTH)
    assert r.status_code == 404


def test_post_then_get_round_trip(client, trace_and_verdict):
    trace_id, jv = trace_and_verdict
    r_post = _post_uv(client, jv)
    assert r_post.status_code == 200
    posted = r_post.json()

    r_get = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH)
    assert r_get.status_code == 200
    got = r_get.json()
    assert got["trace_id"] == trace_id
    assert got["verdict_hash"] == posted["verdict_hash"]
    assert got["signature"] == posted["signature"]
    assert got["universal_verdict"] == posted["universal_verdict"]


def test_repost_with_different_spec_returns_last(client, trace_and_verdict):
    trace_id, jv = trace_and_verdict

    r1 = _post_uv(
        client,
        jv,
        {"spec_id": "spec-A", "criteria_id": "crit-A"},
    )
    assert r1.status_code == 200
    hash_a = r1.json()["verdict_hash"]

    r2 = _post_uv(
        client,
        jv,
        {"spec_id": "spec-B", "criteria_id": "crit-B"},
    )
    assert r2.status_code == 200
    hash_b = r2.json()["verdict_hash"]

    assert hash_a != hash_b

    got = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH).json()
    assert got["verdict_hash"] == hash_b
    assert got["universal_verdict"]["spec_ref"]["spec_id"] == "spec-B"


def test_jamp_and_universal_storage_independent(client, trace_and_verdict, tmp_path):
    trace_id, jv = trace_and_verdict
    r = _post_uv(client, jv)
    assert r.status_code == 200

    audit_path = tmp_path / "audit" / "provenance_traces.jsonl"
    p = AuditPersistence(storage_path=audit_path)

    assert p.read_verdict_by_id(trace_id) is not None
    assert p.read_universal_verdict_by_id(trace_id) is not None
    assert p.verdicts_path != p.universal_verdicts_path
    assert p.verdicts_path.exists()
    assert p.universal_verdicts_path.exists()


def test_both_endpoints_work_on_same_trace(client, trace_and_verdict):
    trace_id, jv = trace_and_verdict
    r = _post_uv(client, jv)
    assert r.status_code == 200

    r_jamp = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert r_jamp.status_code == 200
    assert r_jamp.json()["signature"] == jv["signature"]

    r_uv = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH)
    assert r_uv.status_code == 200
    assert r_uv.json()["universal_verdict"]["execution_ref"]["jamp_verdict_hash"].startswith(
        "sha256:"
    )


def test_repost_appends_not_replaces(client, trace_and_verdict, tmp_path):
    trace_id, jv = trace_and_verdict
    _post_uv(client, jv, {"spec_id": "A", "criteria_id": "A"})
    _post_uv(client, jv, {"spec_id": "B", "criteria_id": "B"})

    audit_path = tmp_path / "audit" / "provenance_traces.jsonl"
    p = AuditPersistence(storage_path=audit_path)

    lines = [
        line
        for line in p.universal_verdicts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 2  # two appends, not replace

    last = p.read_universal_verdict_by_id(trace_id)
    assert last is not None
    assert last["universal_verdict"]["spec_ref"]["spec_id"] == "B"
