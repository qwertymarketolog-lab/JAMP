import json

import pytest

from jamp.runtime.persistence import (
    GENESIS_HASH,
    AuditPersistence,
    _record_hash,
)
from jamp.runtime.provenance import ProvenanceTracker


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
        "execution_details": {
            "provider": "openrouter",
            "provider_response_id": "gen_test_123",
        },
    }

    assert store.write_trace(trace) == "trace_test_001"

    # Raw file: exactly one record, chain metadata present, chain valid.
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    raw = json.loads(lines[0])

    assert raw["prev_hash"] == GENESIS_HASH
    assert "record_hash" in raw
    assert raw["record_hash"] == _record_hash(raw)

    # Original payload fields preserved inside the raw record.
    assert raw["trace_id"] == trace["trace_id"]
    assert raw["decision"] == trace["decision"]
    assert raw["frozen_core"] == trace["frozen_core"]
    assert raw["execution_details"] == trace["execution_details"]
    assert raw["execution_details"]["provider_response_id"] == "gen_test_123"

    # Public read contract: payload without chain metadata.
    read = store.read_trace_by_id("trace_test_001")
    assert read == trace
    assert "prev_hash" not in read
    assert "record_hash" not in read


def test_audit_persistence_requires_trace_id(tmp_path):
    store = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    with pytest.raises(ValueError, match="Trace payload missing required"):
        store.write_trace({"decision": "REFUSE"})


def test_provider_refusal_trace_survives_app_restart(tmp_path):
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

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "REFUSE"
    assert body["reason"] == "PROVIDER_NOT_CONFIGURED"
    trace_id = body["trace_id"]

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
    assert record["refusal_details"]["reason"] == "ZERO_ELIGIBLE_MODELS"


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


def test_attempts_preserved_on_execute(tmp_path):
    """attempts[] из evidence_details сохраняется в trace через AuditPersistence."""
    tracker = ProvenanceTracker()
    trace = tracker.create_trace(
        "search_and_extraction",
        ("C01",),
        "EXECUTE",
        "model-id",
        1,
        evidence_status="VERIFIED",
        evidence_details={
            "provider_model": "z-ai/glm-5.3-flash",
            "attempts": [
                {"attempt": 1, "http_status": 404, "elapsed_ms": 42},
                {"attempt": 2, "http_status": 200, "elapsed_ms": 55},
            ],
        },
    )
    store = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    store.write_trace(trace)
    record = store.read_trace_by_id(trace["trace_id"])
    saved = record["execution_details"]["evidence_details"]["attempts"]
    assert len(saved) == 2
    assert saved[1]["http_status"] == 200


def test_attempts_preserved_on_refuse(tmp_path):
    """attempts[] из failure_diagnostics сохраняется в refusal_details."""
    tracker = ProvenanceTracker()
    trace = tracker.create_trace(
        "search_and_extraction",
        ("C01",),
        "REFUSE",
        "E2_VERIFICATION_INCONCLUSIVE",
        1,
        failure_diagnostics={
            "reason": "API_ERROR",
            "http_status": 404,
            "attempts": [
                {"attempt": i, "http_status": 404, "elapsed_ms": i * 100} for i in range(1, 7)
            ],
        },
    )
    store = AuditPersistence(tmp_path / "provenance_traces.jsonl")
    store.write_trace(trace)
    record = store.read_trace_by_id(trace["trace_id"])
    saved = record["refusal_details"]["provider_diagnostics"]["attempts"]
    assert len(saved) == 6
    assert all(attempt["http_status"] == 404 for attempt in saved)


def test_attempts_invalid_shape_rejected():
    """attempts с элементами неправильной формы отбрасывается."""
    tracker = ProvenanceTracker()
    trace = tracker.create_trace(
        "search_and_extraction",
        ("C01",),
        "EXECUTE",
        "model-id",
        1,
        evidence_status="VERIFIED",
        evidence_details={
            "provider_model": "z-ai/glm-5.3-flash",
            "attempts": [{"attempt": "one", "http_status": 404}],
        },
    )
    assert "attempts" not in trace["execution_details"]["evidence_details"]
