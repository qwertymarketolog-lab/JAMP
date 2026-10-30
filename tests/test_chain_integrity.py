"""Tests for hash-chain integrity in JSONL persistence."""
import json

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth as auth_module
from jamp.api.app import create_app
from jamp.runtime.persistence import (
    GENESIS_HASH,
    AuditPersistence,
    ChainIntegrityError,
    _record_hash,
)

pytestmark = pytest.mark.real_auth

AUTH = {"Authorization": "Bearer test-token"}


def _read_records(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_records(path, records):
    path.write_text(
        "\n".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records
        )
        + "\n",
        encoding="utf-8",
    )


def _p(tmp_path):
    return AuditPersistence(tmp_path / "audit" / "provenance_traces.jsonl")


# --- chain structure ---

def test_first_write_uses_genesis_prev_hash(tmp_path):
    p = _p(tmp_path)
    p.write_verdict("t-1", {"status": "VERIFIED"})

    recs = _read_records(p.verdicts_path)
    assert len(recs) == 1
    assert recs[0]["prev_hash"] == GENESIS_HASH
    assert "record_hash" in recs[0]
    assert recs[0]["record_hash"] == _record_hash(recs[0])


def test_sequential_writes_link_chain(tmp_path):
    p = _p(tmp_path)
    p.write_verdict("t-1", {"status": "VERIFIED"})
    p.write_verdict("t-2", {"status": "CONTRADICTED"})

    recs = _read_records(p.verdicts_path)
    assert recs[0]["prev_hash"] == GENESIS_HASH
    assert recs[1]["prev_hash"] == recs[0]["record_hash"]


def test_read_round_trip_after_writes(tmp_path):
    p = _p(tmp_path)
    p.write_verdict("t-1", {"status": "VERIFIED"})
    p.write_verdict("t-2", {"status": "CONTRADICTED"})

    got = p.read_verdict_by_id("t-1")
    assert got == {"trace_id": "t-1", "status": "VERIFIED"}
    # chain metadata is not exposed to callers
    assert "prev_hash" not in got
    assert "record_hash" not in got


# --- tamper detection ---

def test_tampered_record_breaks_chain(tmp_path):
    p = _p(tmp_path)
    p.write_verdict("t-1", {"status": "VERIFIED"})
    p.write_verdict("t-2", {"status": "CONTRADICTED"})

    recs = _read_records(p.verdicts_path)
    recs[0]["status"] = "CONTRADICTED"  # tamper without recomputing record_hash
    _write_records(p.verdicts_path, recs)

    with pytest.raises(ChainIntegrityError):
        p.read_verdict_by_id("t-1")


def test_deleted_middle_record_breaks_chain(tmp_path):
    p = _p(tmp_path)
    p.write_verdict("t-1", {"status": "VERIFIED"})
    p.write_verdict("t-2", {"status": "CONTRADICTED"})
    p.write_verdict("t-3", {"status": "INCONCLUSIVE"})

    recs = _read_records(p.verdicts_path)
    del recs[1]  # delete middle
    _write_records(p.verdicts_path, recs)

    with pytest.raises(ChainIntegrityError):
        p.read_verdict_by_id("t-1")


# --- legacy compatibility ---

def test_legacy_file_without_chain_markers_is_readable(tmp_path):
    p = _p(tmp_path)
    p.verdicts_path.parent.mkdir(parents=True, exist_ok=True)
    legacy = [
        {"trace_id": "t-legacy-1", "status": "VERIFIED"},
        {"trace_id": "t-legacy-2", "status": "CONTRADICTED"},
    ]
    _write_records(p.verdicts_path, legacy)

    got = p.read_verdict_by_id("t-legacy-1")
    assert got == {"trace_id": "t-legacy-1", "status": "VERIFIED"}


def test_legacy_then_new_write_starts_chain_at_genesis(tmp_path):
    p = _p(tmp_path)
    p.verdicts_path.parent.mkdir(parents=True, exist_ok=True)
    _write_records(
        p.verdicts_path,
        [{"trace_id": "t-legacy-1", "status": "VERIFIED"}],
    )

    p.write_verdict("t-new", {"status": "CONTRADICTED"})

    recs = _read_records(p.verdicts_path)
    assert recs[0].get("prev_hash") is None  # legacy untouched
    assert recs[1]["prev_hash"] == GENESIS_HASH  # new chain starts here
    # chain verifies successfully across legacy + chained mix
    p.read_verdict_by_id("t-new")


# --- API integration ---

@pytest.fixture
def client_and_audit(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda _d: ("VERIFIED", {"reason": "CHAIN_TEST"}),
    )
    monkeypatch.setattr(
        auth_module, "_lookup_by_hash",
        lambda _h: ("test-org", "test", False),
    )

    def _exec(model, payload):
        return {
            "provider": "stub", "model": model,
            "provider_response_id": "chain",
            "provider_model_id": model,
            "content": '{"result":"chain"}',
        }

    audit_path = tmp_path / "audit" / "provenance_traces.jsonl"
    app = create_app(executor=_exec, audit_storage_path=audit_path)
    return TestClient(app), audit_path


def _make_jv(client, req="c-1"):
    r = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "test", "request_id": req},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["trace_id"], body["verdict"]


def test_api_returns_500_on_chain_tampering(client_and_audit):
    client, audit_path = client_and_audit
    trace_id, _ = _make_jv(client)

    vpath = audit_path.parent / "verdicts.jsonl"
    recs = _read_records(vpath)
    recs[0]["status"] = "CONTRADICTED"  # tamper
    _write_records(vpath, recs)

    r = client.get(f"/v1/jamp-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 500
    assert "chain" in r.json()["detail"].lower()


def test_api_returns_500_on_provenance_chain_tampering(client_and_audit):
    client, audit_path = client_and_audit
    trace_id, _ = _make_jv(client)

    recs = _read_records(audit_path)
    recs[0]["trace_id"] = "tampered"  # tamper
    _write_records(audit_path, recs)

    r = client.get(f"/v1/provenance/{trace_id}", headers=AUTH)
    assert r.status_code == 500


def test_api_returns_500_on_uv_chain_tampering(client_and_audit):
    client, audit_path = client_and_audit
    trace_id, jv = _make_jv(client)

    client.post(
        "/v1/universal-verdict",
        json={"jamp_verdict": jv, "spec_id": "s1", "criteria_id": "c1"},
        headers=AUTH,
    )

    upath = audit_path.parent / "universal_verdicts.jsonl"
    recs = _read_records(upath)
    recs[0]["verdict_hash"] = "sha256:" + "0" * 64  # tamper
    _write_records(upath, recs)

    r = client.get(f"/v1/universal-verdict/{trace_id}", headers=AUTH)
    assert r.status_code == 500
