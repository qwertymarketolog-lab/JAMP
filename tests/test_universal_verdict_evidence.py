"""Tests for evidence_refs validation and commitment in UniversalVerdict."""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module
from jamp.api.app import create_app

pytestmark = pytest.mark.real_auth

AUTH = {"Authorization": "Bearer test-token"}
SPEC = {
    "spec_id": "php2shell-remediation-v1",
    "criteria_id": "jamp-patch-verification-v0",
}
REF_HASH = "sha256:" + "a" * 64
SOURCE_HASH = "sha256:" + "b" * 64


@pytest.fixture
def client(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda _d: ("VERIFIED", {"reason": "UV_EVIDENCE_TEST"}),
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
            "provider_response_id": "uv-evidence",
            "provider_model_id": model,
            "content": '{"result":"uv-evidence"}',
        }

    audit_path = tmp_path / "audit" / "provenance_traces.jsonl"
    return TestClient(create_app(executor=_exec, audit_storage_path=audit_path))


@pytest.fixture
def trace_and_verdict(client):
    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "test",
            "request_id": "uve-1",
        },
        headers=AUTH,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return body["trace_id"], body["verdict"]


def _post_uv(client, jv, *, evidence_refs=None, include_refs=False):
    payload = {"jamp_verdict": jv, **SPEC}
    if include_refs:
        payload["evidence_refs"] = evidence_refs
    return client.post(
        "/v1/universal-verdict",
        json=payload,
        headers=AUTH,
    )


def test_omitted_evidence_refs_remains_non_reproducible(client, trace_and_verdict):
    _, jv = trace_and_verdict

    response = _post_uv(client, jv)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["universal_verdict"]["evidence_refs"] == []
    assert body["universal_verdict"]["verifier"]["reproducible"] is False


def test_valid_evidence_refs_are_committed(client, trace_and_verdict):
    _, jv = trace_and_verdict
    refs = [
        {
            "type": "raw_document",
            "ref_hash": REF_HASH,
            "source_sha256": SOURCE_HASH,
        }
    ]

    response = _post_uv(client, jv, evidence_refs=refs, include_refs=True)

    assert response.status_code == 200, response.text
    body = response.json()
    envelope = body["universal_verdict"]

    assert envelope["evidence_refs"] == refs
    assert envelope["verifier"]["reproducible"] is False

    canonical = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
    assert body["verdict_hash"] == expected


def test_evidence_refs_must_be_a_list(client, trace_and_verdict):
    _, jv = trace_and_verdict

    response = _post_uv(client, jv, evidence_refs="", include_refs=True)

    assert response.status_code == 400
    assert response.json()["detail"] == "evidence_refs must be a list"


def test_each_evidence_ref_must_be_an_object(client, trace_and_verdict):
    _, jv = trace_and_verdict

    response = _post_uv(client, jv, evidence_refs=["not-an-object"], include_refs=True)

    assert response.status_code == 400
    assert response.json()["detail"] == "evidence_refs[0] must be an object"


def test_evidence_type_must_be_allowed(client, trace_and_verdict):
    _, jv = trace_and_verdict
    refs = [
        {
            "type": "made_up_type",
            "ref_hash": REF_HASH,
            "source_sha256": SOURCE_HASH,
        }
    ]

    response = _post_uv(
        client, jv, evidence_refs=refs, include_refs=True
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "evidence_refs[0].type not allowed"


def test_ref_hash_must_match_sha256_format(client, trace_and_verdict):
    _, jv = trace_and_verdict
    refs = [
        {
            "type": "raw_document",
            "ref_hash": "sha256:invalid",
            "source_sha256": SOURCE_HASH,
        }
    ]

    response = _post_uv(
        client, jv, evidence_refs=refs, include_refs=True
    )

    assert response.status_code == 400
    assert response.json()["detail"] == ("evidence_refs[0].ref_hash invalid (sha256:<64hex>)")


def test_source_sha256_must_match_sha256_format(client, trace_and_verdict):
    _, jv = trace_and_verdict
    refs = [
        {
            "type": "raw_document",
            "ref_hash": REF_HASH,
            "source_sha256": "not-a-hash",
        }
    ]

    response = _post_uv(
        client, jv, evidence_refs=refs, include_refs=True
    )

    assert response.status_code == 400
    assert response.json()["detail"] == ("evidence_refs[0].source_sha256 invalid")
