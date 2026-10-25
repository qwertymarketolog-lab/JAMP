import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from jamp.provider.groq import DEFAULT_GROQ_MODEL, GroqChatExecutor, GroqError


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def test_groq_executor_posts_openai_compatible_request_and_preserves_identity():
    seen = {}

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["user_agent"] = request.get_header("User-agent")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        seen["timeout"] = timeout
        return Response(
            b'{"id":"chatcmpl-test","model":"llama-3.3-70b-versatile",'
            b'"choices":[{"message":{"content":"hello"}}],"usage":{"total_tokens":2}}'
        )

    executor = GroqChatExecutor("test-secret", opener=fake_open)
    result = executor("groq/default", {"prompt": "hello"})

    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["auth"] == "Bearer test-secret"
    assert seen["user_agent"] == "JAMP-Trust-Layer/1.0"
    assert seen["body"]["model"] == DEFAULT_GROQ_MODEL
    assert seen["body"]["messages"] == [{"role": "user", "content": "hello"}]
    assert seen["body"]["max_tokens"] == 256
    assert seen["timeout"] == 30.0
    assert result["provider"] == "groq"
    assert result["requested_model_id"] == "groq/default"
    assert result["provider_requested_model_id"] == DEFAULT_GROQ_MODEL
    assert result["provider_model_id"] == "llama-3.3-70b-versatile"
    assert result["provider_response_id"] == "chatcmpl-test"
    assert result["content"] == "hello"
    assert result["qualification"] == "UNKNOWN"
    assert "test-secret" not in repr(result)


def test_groq_executor_maps_selected_model():
    seen = {}

    def fake_open(request, timeout):
        seen["model"] = json.loads(request.data.decode("utf-8"))["model"]
        return Response(
            b'{"id":"id-1","model":"llama-3.1-8b-instant","choices":[{"message":{"content":"OK"}}]}'
        )

    executor = GroqChatExecutor(
        "test-secret",
        model_id_map={"am/model-a": "llama-3.1-8b-instant"},
        opener=fake_open,
    )
    result = executor("am/model-a", {"messages": [{"role": "user", "content": "hi"}]})

    assert seen["model"] == "llama-3.1-8b-instant"
    assert result["provider_requested_model_id"] == "llama-3.1-8b-instant"


def test_groq_executor_from_env_requires_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert GroqChatExecutor.from_env() is None


def test_groq_executor_from_env_loads_model_map(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    monkeypatch.setenv("GROQ_MODEL_ID_MAP", '{"am/model-a":"llama-3.1-8b-instant"}')

    executor = GroqChatExecutor.from_env()

    assert executor is not None
    assert executor._model_id_map == {"am/model-a": "llama-3.1-8b-instant"}


def test_groq_executor_rejects_invalid_model_map(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    monkeypatch.setenv("GROQ_MODEL_ID_MAP", "not-json")
    with pytest.raises(ValueError, match="GROQ_MODEL_ID_MAP"):
        GroqChatExecutor.from_env()


def test_groq_executor_fails_closed_on_http_error():
    def fake_open(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":"unauthorized"}'),
        )

    executor = GroqChatExecutor("test-secret", opener=fake_open)
    with pytest.raises(GroqError, match="HTTP 401") as caught:
        executor("llama-3.3-70b-versatile", {"prompt": "hello"})
    assert caught.value.code == "GROQ_HTTP_401"
    assert caught.value.diagnostics == {"provider_http_status": 401}


def test_groq_executor_rejects_missing_prompt_and_bad_response():
    executor = GroqChatExecutor("test-secret", opener=lambda request, timeout: Response(b"{}"))
    with pytest.raises(GroqError, match="prompt or messages"):
        executor("llama-3.3-70b-versatile", {})
    with pytest.raises(GroqError, match="no completion choice"):
        executor("llama-3.3-70b-versatile", {"prompt": "hello"})


def test_groq_executor_refuses_unmapped_internal_model():
    executor = GroqChatExecutor(
        "test-secret",
        opener=lambda request, timeout: pytest.fail("must not call provider"),
    )
    with pytest.raises(GroqError, match="MODEL_NOT_MAPPED") as caught:
        executor("am/unmapped-model", {"prompt": "hello"})
    assert caught.value.code == "MODEL_NOT_MAPPED"
    assert caught.value.diagnostics == {"requested_model_id": "am/unmapped-model"}
