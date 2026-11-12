from __future__ import annotations

from experiments.financial_audit.run_experiment import extract_safe_provider_diagnostics


def test_extracts_safe_diagnostics_from_persisted_refusal_trace() -> None:
    trace = {
        "trace_id": "trace_example",
        "refusal_details": {
            "reason": "PROVIDER_EXECUTION_FAILED",
            "provider_diagnostics": {
                "code": "rate_limit",
                "provider_http_status": 429,
                "http_status": 403,
                "error_body": '{"error":"forbidden"}',
                "network_error": "name resolution failed",
                "exception_type": "TimeoutError",
                "error_message": "request timed out",
                "provider_requested_model_id": "vendor/model",
                "content_len": 0,
                "api_key": "must-not-be-logged",
                "authorization": "Bearer secret",
                "raw_response": {"secret": "nested"},
            },
        },
    }

    assert extract_safe_provider_diagnostics(trace) == {
        "code": "rate_limit",
        "provider_http_status": 429,
        "http_status": 403,
        "error_body": '{"error":"forbidden"}',
        "network_error": "name resolution failed",
        "exception_type": "TimeoutError",
        "error_message": "request timed out",
        "provider_requested_model_id": "vendor/model",
        "content_len": 0,
    }


def test_missing_or_malformed_refusal_diagnostics_return_empty_mapping() -> None:
    assert extract_safe_provider_diagnostics({}) == {}
    assert extract_safe_provider_diagnostics({"refusal_details": None}) == {}
    malformed = {"refusal_details": {"provider_diagnostics": "not-an-object"}}
    assert extract_safe_provider_diagnostics(malformed) == {}
