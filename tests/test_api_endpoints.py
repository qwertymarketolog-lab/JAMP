from fastapi.testclient import TestClient

from jamp.api import create_app


client = TestClient(create_app())


def test_classify_search():
    response = client.post("/v1/classify", json={"intent": "search_and_extraction"})
    assert response.status_code == 200
    assert response.json() == {
        "task_profile": "search_and_extraction",
        "required_capabilities": ["C01", "C06"],
    }


def test_execute_returns_execute_and_provenance():
    response = client.post("/v1/execute", json={"intent": "search_and_extraction"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "EXECUTE"
    provenance = client.get(f"/v1/provenance/{body['trace_id']}")
    assert provenance.status_code == 200
    trace = provenance.json()
    assert (
        trace["gate_evaluator"]["evidence_base_sha256"]
        == "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
    )
    assert trace["frozen_core_state"] == {
        "blob": "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a",
        "delta": 0,
    }


def test_long_context_is_fail_closed():
    response = client.post("/v1/execute", json={"token_count": 16001})
    assert response.status_code == 200
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "ZERO_ELIGIBLE_MODELS"


def test_unknown_task_is_422():
    response = client.post("/v1/execute", json={"intent": "unknown"})
    assert response.status_code == 422
    assert response.json()["status"] == "REFUSE"
