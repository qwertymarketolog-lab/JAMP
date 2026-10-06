import json

import pytest

from jamp.runtime.persistence import AuditPersistence


def test_audit_persistence_write_and_read(tmp_path):
    path = tmp_path / "provenance_traces.jsonl"
    store = AuditPersistence(path)
    trace = {
        "trace_id": "trace_test_001",
        "decision": "EXECUTE",
        "frozen_core": {
            "blob": "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a",
            "delta": 0,
        },
    }

    assert store.write_trace(trace) == "trace_test_001"

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == trace
    assert store.read_trace_by_id("trace_test_001") == trace


def test_audit_persistence_requires_trace_id(tmp_path):
    store = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    with pytest.raises(ValueError, match="Trace payload missing required"):
        store.write_trace({"decision": "REFUSE"})


def test_execute_trace_survives_app_restart(tmp_path):
    from fastapi.testclient import TestClient

    from jamp.api import create_app

    path = tmp_path / "provenance_traces.jsonl"
    with TestClient(create_app(audit_storage_path=path)) as client:
        response = client.post(
            "/v1/execute",
            json={
                "request_id": "req_p24_001",
                "intent": "search_and_extraction",
            },
        )

    assert response.status_code == 200
    trace_id = response.json()["trace_id"]

    with TestClient(create_app(audit_storage_path=path)) as restarted:
        restored = restarted.get(f"/v1/provenance/{trace_id}")

    assert restored.status_code == 200
    trace = restored.json()
    assert trace["request_id"] == "req_p24_001"
    assert trace["frozen_core"]["blob"] == "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
    assert trace["frozen_core"]["delta"] == 0


def test_refuse_trace_is_persisted(tmp_path):
    from fastapi.testclient import TestClient

    from jamp.api import create_app

    path = tmp_path / "provenance_traces.jsonl"
    with TestClient(create_app(audit_storage_path=path)) as client:
        response = client.post(
            "/v1/execute",
            json={
                "request_id": "req_p24_refuse",
                "token_count": 16001,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REFUSE"

    record = AuditPersistence(path).read_trace_by_id(body["trace_id"])
    assert record is not None
    assert record["request_id"] == "req_p24_refuse"
    assert record["refusal_details"]["reason"] == "FAIL_CLOSED_ZERO_QUALIFIED_MODELS"


def test_unknown_task_persists_refusal_trace(tmp_path):
    from fastapi.testclient import TestClient

    from jamp.api import create_app

    path = tmp_path / "provenance_traces.jsonl"
    with TestClient(create_app(audit_storage_path=path)) as client:
        response = client.post(
            "/v1/execute",
            json={"request_id": "req_p24_unknown", "intent": "unknown"},
        )

    assert response.status_code == 422
    trace_id = response.json()["trace_id"]
    record = AuditPersistence(path).read_trace_by_id(trace_id)
    assert record is not None
    assert record["status"] == "REFUSE"
