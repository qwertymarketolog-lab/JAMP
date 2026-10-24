from fastapi.testclient import TestClient

from jamp.api import create_app


def test_classify_search():
    client = TestClient(create_app(executor=lambda model, payload: {"content": "unused"}))
    response = client.post("/v1/classify", json={"intent": "search_and_extraction"})
    assert response.status_code == 200
    assert response.json() == {
        "task_profile": "search_and_extraction",
        "required_capabilities": ["C01", "C06"],
    }


def test_execute_returns_execute_and_provenance():
    client = TestClient(
        create_app(executor=lambda model, payload: {"model": model, "content": "test result"})
    )
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Say hello", "request_id": "test-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "EXECUTE"
    assert body["output"]["content"] == "test result"
    provenance = client.get(f"/v1/provenance/{body['trace_id']}")
    assert provenance.status_code == 200
    trace = provenance.json()
    assert (
        trace["gate_evaluator"]["evidence_base_sha256"]
        == "7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
    )
    assert trace["execution_details"]["output_digest"].startswith("sha256:")
    assert trace["frozen_core_state"] == {
        "blob": "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a",
        "delta": 0,
    }


def test_execute_without_provider_fails_closed(monkeypatch):
    monkeypatch.delenv("ANYMODEL_API_KEY", raising=False)
    client = TestClient(create_app())
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Say hello"},
    )
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "REFUSE"
    trace = client.get(f"/v1/provenance/{body['trace_id']}").json()
    assert trace["status"] == "REFUSE"
    assert trace["refusal_details"]["reason"] == "PROVIDER_NOT_CONFIGURED"


def test_provider_failure_is_recorded_and_refused():
    def broken_executor(model, payload):
        raise RuntimeError("do not expose this internal error")

    client = TestClient(create_app(executor=broken_executor))
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Say hello"},
    )
    assert response.status_code == 502
    assert response.json()["reason"] == "EXECUTOR_ERROR"
    assert "do not expose" not in response.text


def test_long_context_is_fail_closed():
    client = TestClient(create_app(executor=lambda model, payload: {"content": "unused"}))
    response = client.post("/v1/execute", json={"token_count": 16001})
    assert response.status_code == 200
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "ZERO_ELIGIBLE_MODELS"


def test_unknown_task_is_422():
    client = TestClient(create_app(executor=lambda model, payload: {"content": "unused"}))
    response = client.post("/v1/execute", json={"intent": "unknown"})
    assert response.status_code == 422
    assert response.json()["status"] == "REFUSE"

def test_provider_http_diagnostics_survive_provenance():
    from jamp.provider.openrouter import OpenRouterError

    def failing_executor(model, payload):
        raise OpenRouterError(
            "provider request failed",
            code="OPENROUTER_HTTP_429",
            diagnostics={"provider_http_status": 429},
        )

    client = TestClient(create_app(executor=failing_executor))
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Say hello"},
    )

    assert response.status_code == 502
    body = response.json()
    trace = client.get(f"/v1/provenance/{body['trace_id']}").json()
    diagnostics = trace["refusal_details"]["provider_diagnostics"]
    assert diagnostics["code"] == "OPENROUTER_HTTP_429"
    assert diagnostics["provider_http_status"] == 429
