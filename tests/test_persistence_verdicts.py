from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from jamp.api import app as app_module
from jamp.api.app import create_app
from jamp.runtime.persistence import (
    GENESIS_HASH,
    AuditPersistence,
    _record_hash,
)


def test_write_and_read_verdict_round_trip(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    payload = {
        "trace_id": "trace-1",
        "status": "VERIFIED",
        "signature": "signed-value",
        "aggregate_status": "VERIFIED",
    }

    assert persistence.write_verdict("trace-1", payload) == "trace-1"
    assert persistence.read_verdict_by_id("trace-1") == payload
    assert persistence.verdicts_path == tmp_path / "verdicts.jsonl"


def test_unknown_verdict_returns_none(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")

    assert persistence.read_verdict_by_id("missing-trace") is None


def test_missing_verdict_file_returns_none(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")

    assert not persistence.verdicts_path.exists()
    assert persistence.read_verdict_by_id("trace-1") is None


def test_trace_and_verdict_storage_are_independent(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    trace = {"trace_id": "trace-1", "status": "EXECUTE"}
    verdict = {"trace_id": "trace-1", "status": "VERIFIED", "signature": "sig"}

    persistence.write_trace(trace)
    persistence.write_verdict("trace-1", verdict)

    assert persistence.read_trace_by_id("trace-1") == trace
    assert persistence.read_verdict_by_id("trace-1") == verdict
    assert persistence.storage_path != persistence.verdicts_path


def test_multiple_verdicts_are_appended_without_overwriting(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    first = {"status": "VERIFIED", "signature": "sig-1"}
    second = {"status": "INCONCLUSIVE", "signature": "sig-2"}

    persistence.write_verdict("trace-1", first)
    persistence.write_verdict("trace-2", second)

    records = [
        json.loads(line)
        for line in persistence.verdicts_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 2

    # Original payload fields preserved inside both raw records.
    for record, payload, tid in [
        (records[0], first, "trace-1"),
        (records[1], second, "trace-2"),
    ]:
        assert record["trace_id"] == tid
        assert record["status"] == payload["status"]
        assert record["signature"] == payload["signature"]

    # Chain linkage: first record is genesis, second points to first.
    assert records[0]["prev_hash"] == GENESIS_HASH
    assert records[1]["prev_hash"] == records[0]["record_hash"]
    assert records[0]["record_hash"] == _record_hash(records[0])
    assert records[1]["record_hash"] == _record_hash(records[1])

    # Public read contract: payload without chain metadata.
    assert persistence.read_verdict_by_id("trace-1") == {**first, "trace_id": "trace-1"}
    assert persistence.read_verdict_by_id("trace-2") == {**second, "trace_id": "trace-2"}


def test_write_verdict_rejects_empty_trace_id(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")

    with pytest.raises(ValueError, match="trace_id"):
        persistence.write_verdict("", {"status": "VERIFIED"})


def test_explicit_trace_id_overrides_payload_trace_id(tmp_path):
    persistence = AuditPersistence(tmp_path / "provenance_traces.jsonl")

    persistence.write_verdict(
        "trace-authoritative",
        {"trace_id": "trace-untrusted", "status": "VERIFIED"},
    )

    assert persistence.read_verdict_by_id("trace-authoritative") == {
        "trace_id": "trace-authoritative",
        "status": "VERIFIED",
    }
    assert persistence.read_verdict_by_id("trace-untrusted") is None


def test_execute_persists_signed_verdict(tmp_path, monkeypatch):
    monkeypatch.setenv("JAMP_SIGNING_KEY", "test-signing-key")
    monkeypatch.setattr(app_module, "verify_generation", lambda _output: ("VERIFIED", {}))

    def executor(_model: str, _payload: dict):
        return {
            "provider": "openrouter",
            "provider_model_id": "test/provider-model",
            "provider_response_id": "response-1",
            "content": "JAMP test output",
        }

    storage_path = tmp_path / "provenance_traces.jsonl"
    app = create_app(executor=executor, audit_storage_path=storage_path)
    client = TestClient(app)
    response = client.post(
        "/v1/execute",
        headers={"Authorization": "Bearer test-api-key"},
        json={"intent": "search_and_extraction", "prompt": "Return a short test result."},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "EXECUTE"
    verdict = body["verdict"]
    assert verdict["trace_id"] == body["trace_id"]
    assert verdict["signature"]
    stored = AuditPersistence(storage_path).read_verdict_by_id(body["trace_id"])
    assert stored == verdict
    assert stored["aggregate_status"] == body["aggregate_status"]
