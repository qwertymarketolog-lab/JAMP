from __future__ import annotations

import base64
import hashlib
import json

import pytest\n\nfrom jamp.provider.anymodel import AnyModelChatExecutor, AnyModelBudgetError\nfrom scripts.research import run_experiment_v4 as experiment_v4


def test_mock_probe_scenarios_are_network_free() -> None:
    result = experiment_v4.run_mock()
    assert result["network"] == "DISABLED"
    assert [item["reason"] for item in result["results"]] == [
        "MOCK_DETECTED", "MOCK_DETECTED", "MOCK_DETECTED", None
    ]


def test_mock_response_id_is_refused() -> None:
    status, reason = experiment_v4.preflight_response(
        experiment_v4.DEFAULT_MODEL,
        {
            "provider_model_id": experiment_v4.DEFAULT_MODEL,
            "provider_response_id": "chatcmpl-abc123",
            "content": "OK",
        },
    )
    assert (status, reason) == ("REFUSE", "MOCK_DETECTED")


def test_mock_response_model_is_refused() -> None:
    status, reason = experiment_v4.preflight_response(
        experiment_v4.DEFAULT_MODEL,
        {"provider_model_id": "openai/gpt-5", "provider_response_id": "chatcmpl-real-1",
         "content": "OK"},
    )
    assert (status, reason) == ("REFUSE", "MOCK_DETECTED")


def test_mock_response_text_is_refused() -> None:
    status, reason = experiment_v4.preflight_response(
        experiment_v4.DEFAULT_MODEL,
        {
            "provider_model_id": experiment_v4.DEFAULT_MODEL,
            "provider_response_id": "chatcmpl-real-1",
            "content": "Hi! I'm an AI assistant",
        },
    )
    assert (status, reason) == ("REFUSE", "MOCK_DETECTED")


def test_model_mismatch_is_refused() -> None:
    status, reason = experiment_v4.preflight_response(
        experiment_v4.DEFAULT_MODEL,
        {"provider_model_id": "ag/other-model", "provider_response_id": "cmpl-real-1",
         "content": "OK"},
    )
    assert (status, reason) == ("REFUSE", "MODEL_MISMATCH")


def test_matching_non_mock_response_passes_preflight() -> None:
    status, reason = experiment_v4.preflight_response(
        experiment_v4.DEFAULT_MODEL,
        {
            "provider_model_id": experiment_v4.DEFAULT_MODEL,
            "provider_response_id": "cmpl-live-shaped-1",
            "content": "The price of BTC is $65000.",
        },
    )
    assert (status, reason) == ("PREFLIGHT_OK", None)


def test_price_gate_refuses_before_any_request(monkeypatch) -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network/provider must not be called")

    monkeypatch.setattr("scripts.research.run_experiment_v4.AnyModelChatExecutor", forbidden)
    result = experiment_v4.run_live_cycle(
        "Say exactly: OK", experiment_v4.DEFAULT_MODEL, price_confirmed=False,
        price_source=None, confirmed_price_usd=None, api_key="test-key",
    )
    assert result == {
        "status": "REFUSE", "reason": "PRICE_NOT_CONFIRMED", "http_request_made": False,
    }
    assert called is False


def test_manual_price_attestation_requires_source_and_positive_price() -> None:
    assert experiment_v4._price_attestation(True, "", 0.01) is None
    assert experiment_v4._price_attestation(True, "pricing page", 0) is None
    assert experiment_v4._price_attestation(True, "pricing page", 0.01) == {
        "manual_confirmation": True, "price_source": "pricing page",
        "confirmed_price_usd": 0.01,
    }


def test_raw_hash_calculation_is_stable() -> None:
    body = b'{"model":"ag/claude-sonnet-4-6"}'
    representation = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + body
    assert hashlib.sha256(body).hexdigest() == hashlib.sha256(
        base64.b64decode(base64.b64encode(body))
    ).hexdigest()
    assert len(hashlib.sha256(representation).hexdigest()) == 64


def test_mock_output_is_json_serializable() -> None:
    assert json.loads(json.dumps(experiment_v4.run_mock()))["mode"] == "MOCK"


def test_preflight_success_reaches_mocked_e4(monkeypatch) -> None:
    e4_calls = []

    class FakeExecutor:
        def __init__(self, api_key, *, opener):
            self.opener = opener

        def __call__(self, selected_model, payload):
            assert selected_model == experiment_v4.DEFAULT_MODEL
            assert payload == {"prompt": "The price of BTC is $65000."}
            return {
                "provider_model_id": experiment_v4.DEFAULT_MODEL,
                "provider_response_id": "cmpl-test-real-shaped",
                "content": "The price of BTC is $65000.",
            }

    def fake_e4(content, trace_id):
        e4_calls.append((content, trace_id))
        return {"verdict": "INCONCLUSIVE", "reason": "MOCK_E4"}

    monkeypatch.setattr(experiment_v4, "AnyModelChatExecutor", FakeExecutor)
    monkeypatch.setattr(
        experiment_v4, "_finalize_raw",
        lambda capture: {"http_representation_sha256": "a" * 64},
    )
    monkeypatch.setattr(experiment_v4, "_e4_verify", fake_e4)
    result = experiment_v4.run_live_cycle(
        "The price of BTC is $65000.", experiment_v4.DEFAULT_MODEL,
        price_confirmed=True, price_source="test-only price attestation",
        confirmed_price_usd=0.01, full_cycle=True, api_key="test-key",
    )
    assert result["e2_preflight"] == "PREFLIGHT_OK"
    assert result["e4"] == {"verdict": "INCONCLUSIVE", "reason": "MOCK_E4"}
    assert len(e4_calls) == 1


def test_mock_response_never_reaches_e4(monkeypatch) -> None:
    e4_called = False

    class FakeExecutor:
        def __init__(self, api_key, *, opener):
            self.opener = opener

        def __call__(self, selected_model, payload):
            return {
                "provider_model_id": "openai/gpt-5",
                "provider_response_id": "cmpl-mock",
                "content": "The price of BTC is $65000.",
            }

    def forbidden_e4(content, trace_id):
        nonlocal e4_called
        e4_called = True
        raise AssertionError("E4 must not receive a mock response")

    monkeypatch.setattr(experiment_v4, "AnyModelChatExecutor", FakeExecutor)
    monkeypatch.setattr(
        experiment_v4, "_finalize_raw",
        lambda capture: {"http_representation_sha256": "b" * 64},
    )
    monkeypatch.setattr(experiment_v4, "_e4_verify", forbidden_e4)
    result = experiment_v4.run_live_cycle(
        "Say exactly: OK", experiment_v4.DEFAULT_MODEL,
        price_confirmed=True, price_source="test-only price attestation",
        confirmed_price_usd=0.01, full_cycle=True, api_key="test-key",
    )
    assert result["status"] == "REFUSE"
    assert result["reason"] == "MOCK_DETECTED"
    assert e4_called is False



def test_missing_provider_reported_model_is_refused() -> None:
    status, reason = experiment_v4.preflight_response(
        experiment_v4.DEFAULT_MODEL,
        {
            "model": experiment_v4.DEFAULT_MODEL,
            "provider_response_id": "cmpl-real-2",
            "content": "OK",
        },
    )
    assert (status, reason) == ("REFUSE", "MODEL_ID_MISSING")



def test_anymodel_execute_requires_explicit_max_tokens() -> None:
    executor = AnyModelChatExecutor("test-key", opener=lambda request, timeout: None)
    with pytest.raises(ValueError, match="max_tokens"):
        executor.execute(
            experiment_v4.DEFAULT_MODEL, {"prompt": "SBER costs 299 RUB"},
            max_budget_usd=0.01,
        )


def test_anymodel_execute_sends_max_tokens_256_to_mock() -> None:
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"id":"cmpl-mock-success","model":"ag/claude-sonnet-4-6",'
                b'"choices":[{"message":{"content":"SBER costs 299 RUB"}}]}'
            )

    def fake_opener(request, timeout):
        observed["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    executor = AnyModelChatExecutor("test-key", opener=fake_opener)
    result = executor.execute(
        experiment_v4.DEFAULT_MODEL,
        {"prompt": "SBER costs 299 RUB"},
        max_tokens=256,
        max_budget_usd=0.01,
        max_input_tokens=8192,
    )
    assert observed["body"]["max_tokens"] == 256
    assert result["content"] == "SBER costs 299 RUB"


def test_anymodel_execute_refuses_budget_before_network() -> None:
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be called over budget")

    executor = AnyModelChatExecutor("test-key", opener=forbidden)
    with pytest.raises(AnyModelBudgetError, match="BUDGET_EXCEEDED"):
        executor.execute(
            experiment_v4.DEFAULT_MODEL,
            {"prompt": "SBER costs 299 RUB"},
            max_tokens=100000,
            max_budget_usd=0.01,
            max_input_tokens=8192,
        )
    assert called is False


def test_live_cycle_refuses_over_budget_without_http(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("provider must not be constructed for an over-budget call")

    monkeypatch.setattr(experiment_v4, "AnyModelChatExecutor", forbidden)
    result = experiment_v4.run_live_cycle(
        "SBER costs 299 RUB", experiment_v4.DEFAULT_MODEL,
        price_confirmed=True, price_source="test price source",
        confirmed_price_usd=0.01, api_key="test-key",
        max_tokens=100000, max_budget_usd=0.01,
    )
    assert result["status"] == "REFUSE"
    assert result["reason"] == "BUDGET_EXCEEDED"
    assert result["http_request_made"] is False
