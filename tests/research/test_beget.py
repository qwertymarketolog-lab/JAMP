from __future__ import annotations

import hashlib
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from jamp.provider.beget import BegetChatExecutor, DEFAULT_BASE_URL


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def pricing_file(tmp_path, model_id: str = "catalog/model-a"):
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps({
        "version": 1,
        "snapshot_date": "2026-11-18",
        "currency": "RUB",
        "models": {
            model_id: {
                "input_rub_per_million": 100,
                "output_rub_per_million": 200,
            }
        },
    }), encoding="utf-8")
    return path


def test_beget_http_200_parses_usage_and_calculates_rub_cost(tmp_path) -> None:
    observed = {}
    raw = json.dumps({
        "id": "chatcmpl-beget-test",
        "model": "catalog/model-a",
        "choices": [{"message": {"content": "verified transport"}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
    }).encode()

    def fake_opener(request, timeout):
        observed["url"] = request.full_url
        observed["authorization"] = request.get_header("Authorization")
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        observed["timeout"] = timeout
        return FakeResponse(raw)

    executor = BegetChatExecutor(
        "test-secret", opener=fake_opener, pricing_path=pricing_file(tmp_path)
    )
    result = executor.execute("catalog/model-a", [{"role": "user", "content": "hello"}], 128)

    assert observed["url"] == f"{DEFAULT_BASE_URL}/chat/completions"
    assert observed["authorization"] == "Bearer test-secret"
    assert observed["payload"]["model"] == "catalog/model-a"
    assert observed["payload"]["max_tokens"] == 128
    assert observed["timeout"] == 30.0
    assert result["usage"]["total_tokens"] == 1500
    assert result["content"] == "verified transport"
    assert result["cost_estimate_rub"] == "0.20000000"
    assert result["raw_body"] == raw.decode()
    assert result["raw_body_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["error"] is None


def test_beget_http_401_returns_safe_error_and_raw_body(tmp_path) -> None:
    raw = b'{"error":"invalid api key"}'

    def unauthorized(request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, BytesIO(raw))

    executor = BegetChatExecutor(
        "test-secret",
        opener=unauthorized,
        pricing_path=pricing_file(tmp_path),
    )
    result = executor.execute("catalog/model-a", [{"role": "user", "content": "hello"}], 64)

    assert result["error"] == {
        "type": "HTTPError",
        "code": "HTTP_401",
        "message": "Beget returned HTTP 401",
        "http_status": 401,
    }
    assert result["raw_body"] == raw.decode()
    assert result["raw_body_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["cost_estimate_rub"] == "UNKNOWN"
    assert "test-secret" not in json.dumps(result)


def test_beget_timeout_is_fail_closed_and_never_reports_zero_cost(tmp_path) -> None:
    def timeout(request, timeout):
        raise TimeoutError("simulated timeout")

    executor = BegetChatExecutor("test-secret", opener=timeout, pricing_path=pricing_file(tmp_path))
    result = executor.execute("catalog/model-a", [{"role": "user", "content": "hello"}], 64)

    assert result["error"]["code"] == "TIMEOUT"
    assert result["raw_body"] is None
    assert result["cost_estimate_rub"] == "UNKNOWN"


def test_beget_unknown_model_id_or_missing_usage_has_unknown_cost(tmp_path) -> None:
    raw = (
        b'{"model":"unmapped/model","choices":[{"message":{"content":"ok"}}],'
        b'"usage":{"prompt_tokens":1,"completion_tokens":1}}'
    )
    executor = BegetChatExecutor(
        "test-secret",
        opener=lambda request, timeout: FakeResponse(raw),
        pricing_path=pricing_file(tmp_path),
    )
    result = executor.execute("unmapped/model", [{"role": "user", "content": "hello"}], 64)
    assert result["cost_estimate_rub"] == "UNKNOWN"

    raw_missing_usage = b'{"model":"catalog/model-a","choices":[{"message":{"content":"ok"}}]}'
    executor = BegetChatExecutor(
        "test-secret",
        opener=lambda request, timeout: FakeResponse(raw_missing_usage),
        pricing_path=pricing_file(tmp_path),
    )
    result = executor.execute("catalog/model-a", [{"role": "user", "content": "hello"}], 64)
    assert result["cost_estimate_rub"] == "UNKNOWN"


def test_beget_from_env_uses_documented_defaults(monkeypatch) -> None:
    monkeypatch.setenv("BEGET_API_KEY", "test-secret")
    monkeypatch.delenv("BEGET_BASE_URL", raising=False)
    executor = BegetChatExecutor.from_env()
    assert executor is not None
    assert executor._chat_url == f"{DEFAULT_BASE_URL}/chat/completions"


def test_beget_is_not_configured_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("BEGET_API_KEY", raising=False)
    assert BegetChatExecutor.from_env() is None


def test_beget_rejects_invalid_messages_and_max_tokens() -> None:
    executor = BegetChatExecutor("test-secret", opener=lambda request, timeout: None)
    with pytest.raises(ValueError, match="messages"):
        executor.execute("catalog/model-a", [], 64)
    with pytest.raises(ValueError, match="max_tokens"):
        executor.execute("catalog/model-a", [{"role": "user", "content": "hello"}], 0)
