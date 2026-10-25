from __future__ import annotations

from jamp.runtime import qualification


def test_registered_benchmark_qualification_is_returned(monkeypatch):
    monkeypatch.setitem(
        qualification.QUALIFICATION_REGISTRY,
        ("fixture/model-qualified", "search_and_extraction"),
        "QUALIFIED",
    )

    assert (
        qualification.evaluate_model_qualification(
            "fixture/model-qualified", "search_and_extraction"
        )
        == "QUALIFIED"
    )


def test_unknown_model_fails_closed_to_unknown():
    assert (
        qualification.evaluate_model_qualification("unknown/model", "search_and_extraction")
        == "UNKNOWN"
    )


def test_single_successful_financial_audit_does_not_qualify_glm():
    assert (
        qualification.evaluate_model_qualification("z-ai/glm-5.3-flash", "search_and_extraction")
        == "UNKNOWN"
    )


def test_invalid_model_or_task_fails_closed():
    assert qualification.evaluate_model_qualification("", "search_and_extraction") == "UNKNOWN"
    assert qualification.evaluate_model_qualification("fixture/model-qualified", "") == "UNKNOWN"


def test_execute_returns_qualification_and_records_it_in_trace(monkeypatch):
    import importlib

    from fastapi.testclient import TestClient

    app_module = importlib.import_module("jamp.api.app")
    monkeypatch.setenv("JAMP_SIGNING_KEY", "qualification-test-key")
    monkeypatch.setenv("JAMP_ENV", "test")
    monkeypatch.setattr(
        app_module, "verify_generation", lambda output: ("VERIFIED", {"reason": "TEST_VERIFIED"})
    )

    client = TestClient(
        app_module.create_app(
            executor=lambda model, payload: {
                "provider": "openrouter",
                "model": model,
                "provider_response_id": "generation-qualification-test",
                "provider_model_id": "z-ai/glm-5.3-flash",
                "content": "reference values extracted",
            }
        )
    )
    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "Extract the reference values"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_status"] == "VERIFIED"
    assert body["qualification"] == "UNKNOWN"
    trace = client.get(f"/v1/provenance/{body['trace_id']}").json()
    assert trace["execution_details"]["qualification"] == "UNKNOWN"
