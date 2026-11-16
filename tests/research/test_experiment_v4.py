from __future__ import annotations

import base64
import hashlib
import json

import pytest

from jamp.provider.anymodel import (
    DEFAULT_USER_AGENT,
    AnyModelBudgetError,
    AnyModelChatExecutor,
)
from scripts.research import run_experiment_v4 as experiment_v4


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

        def execute(
            self, selected_model, payload, *, max_tokens, max_budget_usd, max_input_tokens
        ):
            assert selected_model == experiment_v4.DEFAULT_MODEL
            assert payload == {"prompt": "The price of BTC is $65000."}
            assert max_tokens == 256
            assert max_budget_usd == 0.01
            assert max_input_tokens == 8192
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
        max_tokens=256, max_budget_usd=0.01,
    )
    assert result["e2_preflight"] == "PREFLIGHT_OK"
    assert result["e4"] == {"verdict": "INCONCLUSIVE", "reason": "MOCK_E4"}
    assert len(e4_calls) == 1


def test_mock_response_never_reaches_e4(monkeypatch) -> None:
    e4_called = False

    class FakeExecutor:
        def __init__(self, api_key, *, opener):
            self.opener = opener

        def execute(
            self, selected_model, payload, *, max_tokens, max_budget_usd, max_input_tokens
        ):
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
        max_tokens=256, max_budget_usd=0.01,
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
        observed["user_agent"] = request.get_header("User-agent")
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
    assert observed["user_agent"] == DEFAULT_USER_AGENT
    assert DEFAULT_USER_AGENT == "JAMP-GPT-6-Astra-API-Probe/1.0"
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



def test_legacy_anymodel_call_logs_512_token_compatibility(caplog) -> None:
    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    def fake_opener(request, timeout):
        observed["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    executor = AnyModelChatExecutor("test-key", opener=fake_opener)
    executor(experiment_v4.DEFAULT_MODEL, {"prompt": "Hi"})
    assert observed["body"]["max_tokens"] == 512
    assert "Legacy AnyModelChatExecutor.__call__" in caplog.text



def test_live_cycle_preserves_redacted_http_error_diagnostics(monkeypatch) -> None:
    from email.message import Message
    from io import BytesIO
    from urllib.error import HTTPError

    api_key = "sk-test-secret-1234567890"
    headers = Message()
    headers["Content-Type"] = "application/json"
    headers["X-RateLimit-Remaining"] = "0"
    headers["X-Diagnostic"] = api_key
    body = b'{"error":"Rate limit exceeded","credential":"sk-provider-secret-1234567890"}'

    class FailingExecutor:
        def __init__(self, api_key, *, opener):
            self.api_key = api_key

        def execute(self, *args, **kwargs):
            raise HTTPError(
                "https://anymodel.invalid/v1/chat/completions", 429,
                "Too Many Requests", headers, BytesIO(body),
            )

    monkeypatch.setattr(experiment_v4, "AnyModelChatExecutor", FailingExecutor)
    result = experiment_v4.run_live_cycle(
        "Say exactly: OK", experiment_v4.DEFAULT_MODEL,
        price_confirmed=True, price_source="test pricing source",
        confirmed_price_usd=0.01, api_key=api_key,
        max_tokens=256, max_budget_usd=0.01,
    )

    serialized = json.dumps(result)
    assert result["status"] == "INCONCLUSIVE"
    assert result["http_request_made"] is True
    assert result["error_type"] == "HTTPError"
    assert result["http_status"] == 429
    assert result["http_reason"] == "Too Many Requests"
    assert "Rate limit exceeded" in result["error_body"]
    assert ["X-RateLimit-Remaining", "0"] in result["error_headers"]
    assert api_key not in serialized
    assert "sk-provider-secret-1234567890" not in serialized
    assert "[REDACTED]" in serialized


def test_anymodel_executor_does_not_swallow_http_error() -> None:
    from io import BytesIO
    from urllib.error import HTTPError

    failure = HTTPError(
        "https://anymodel.invalid/v1/chat/completions", 401,
        "Unauthorized", {}, BytesIO(b'{"error":"invalid key"}'),
    )

    def failing_opener(request, timeout):
        raise failure

    executor = AnyModelChatExecutor("test-key", opener=failing_opener)
    with pytest.raises(HTTPError) as captured:
        executor.execute(
            experiment_v4.DEFAULT_MODEL, {"prompt": "Say exactly: OK"},
            max_tokens=256, max_budget_usd=0.01, max_input_tokens=8192,
        )
    assert captured.value.code == 401


def test_live_e4_prompt_extracts_sber_rub_price_claim(monkeypatch) -> None:
    claims = experiment_v4.extract_claims(
        "The price of SBER is 300 RUB", trace_id="test-sber"
    )
    assert len(claims) == 1
    assert claims[0].claim_type == "price"
    assert claims[0].ticker == "SBER"
    assert claims[0].cited_value == 300.0
    assert claims[0].currency == "RUB"


def test_live_e4_cli_mode_uses_fixed_prompt_and_limits(monkeypatch, tmp_path) -> None:
    captured = {}

    def fake_cycle(prompt, model, **kwargs):
        captured.update(prompt=prompt, model=model, **kwargs)
        return {"status": "OBSERVED", "e4": {"verdict": "VERIFIED"}}

    monkeypatch.setattr(experiment_v4, "run_live_cycle", fake_cycle)
    monkeypatch.setattr(
        "sys.argv",
        ["run_experiment_v4.py", "--live-e4", "--confirm-live",
         "--price-confirmed", "--price-source", "test",
         "--confirmed-price-usd", "0.001", "--output-dir", str(tmp_path)],
    )
    assert experiment_v4.main() == 0
    assert captured["prompt"] == experiment_v4.LIVE_E4_PROMPT
    assert captured["full_cycle"] is True
    assert captured["max_tokens"] == 256
    assert captured["max_budget_usd"] == 0.01


def test_mock_e2_e4_runs_real_extractor_and_preserves_mock_raw(monkeypatch) -> None:
    result = experiment_v4.run_mock_e4()
    assert result["mode"] == "MOCK_E2_E4"
    assert result["network"] == "DISABLED"
    assert result["e2_preflight"] == "PREFLIGHT_OK"
    assert result["e4"]["verdict"] == "VERIFIED"
    assert result["e4"]["extracted_claim"]["type"] == "price"
    assert result["e4"]["extracted_claim"]["unit"] == "RUB"
    assert result["e4"]["raw_evidence"][0]["body_complete"] is True


def test_e4_moex_verifier_can_return_contradicted_with_raw_evidence() -> None:
    body = b'{"mock":true,"ticker":"SBER","last":301.0}'

    def contradicted_moex(ticker, claim_type, claimed_value, **kwargs):
        assert (ticker, claim_type, claimed_value) == ("SBER", "price", 300.0)
        return experiment_v4.E4_CONTRADICTED, {
            "result": "CONTRADICTED",
            "raw_evidence": [{
                "status_code": 200, "body_complete": True,
                "raw_body_base64": base64.b64encode(body).decode("ascii"),
                "sha256_body": hashlib.sha256(body).hexdigest(),
            }],
        }

    result = experiment_v4._e4_verify(
        "The price of SBER is 300 RUB", "test-contradicted",
        moex_verifier=contradicted_moex,
    )
    assert result["verdict"] == "CONTRADICTED"


# Literal replay of the provider response captured in live run 43805799030.
SBER_REFUSAL_REPLAY = (
    "I can't retrieve live stock prices. "
    "To get the current SBER price, check a financial service like Moex, "
    "Yahoo Finance, or your broker."
)


def test_e4_replay_without_price_claim_is_inconclusive() -> None:
    result = experiment_v4._e4_verify(SBER_REFUSAL_REPLAY, "replay-43805799030")
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["reason"] == "NO_PRICE_CLAIM"
    assert len(result["extracted_claim"]) == 2
    assert all(item["type"] == "other" for item in result["extracted_claim"])
    assert result["raw_evidence"] == []


def test_e4_multiple_sber_price_claims_are_ambiguous(monkeypatch) -> None:
    first = experiment_v4.extract_claims(
        "The price of SBER is 300 RUB", trace_id="multiple-sber-1"
    )
    second = experiment_v4.extract_claims(
        "The price of SBER is 301 RUB", trace_id="multiple-sber-2"
    )
    monkeypatch.setattr(
        experiment_v4, "extract_claims", lambda content, trace_id: first + second
    )

    def forbidden_moex(*args, **kwargs):
        raise AssertionError("ambiguous claims must not reach MOEX")

    result = experiment_v4._e4_verify(
        "ignored replay input", "multiple-sber", moex_verifier=forbidden_moex
    )
    assert result["verdict"] == "AMBIGUOUS"
    assert result["reason"] == "MULTIPLE_PRICE_CLAIMS"
    assert len(result["extracted_claim"]) == 2
    assert result["raw_evidence"] == []
