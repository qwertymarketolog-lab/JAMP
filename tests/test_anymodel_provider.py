import json

import pytest

from jamp.provider.anymodel import AnyModelChatExecutor, AnyModelError


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


def test_executor_posts_selected_model_and_returns_content():
    observed = {}

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["authorization"] = request.get_header("Authorization")
        observed["body"] = json.loads(request.data.decode("utf-8"))
        observed["timeout"] = timeout
        return FakeResponse(
            json.dumps(
                {
                    "id": "chatcmpl-test",
                    "choices": [{"message": {"content": "Hello from AnyModel"}}],
                    "usage": {"total_tokens": 12},
                }
            ).encode("utf-8")
        )

    executor = AnyModelChatExecutor("test-secret", opener=fake_urlopen)
    result = executor("ag/gemini-3.7-flash-high", {"prompt": "Say hello"})

    assert observed["url"] == "https://anymodel.org/v1/chat/completions"
    assert observed["authorization"] == "Bearer test-secret"
    assert observed["body"]["model"] == "ag/gemini-3.7-flash-high"
    assert observed["body"]["messages"] == [{"role": "user", "content": "Say hello"}]
    assert observed["timeout"] == 30.0
    assert result["content"] == "Hello from AnyModel"
    assert result["provider_response_id"] == "chatcmpl-test"
    assert result["usage"] == {"total_tokens": 12}


def test_executor_accepts_valid_messages():
    executor = AnyModelChatExecutor(
        "test-secret",
        opener=lambda request, timeout: FakeResponse(
            b'{"choices":[{"message":{"content":"ok"}}]}'
        ),
    )
    result = executor(
        "ag/gemini-3.7-flash-high",
        {"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert result["content"] == "ok"


def test_executor_refuses_missing_prompt():
    executor = AnyModelChatExecutor("test-secret")
    with pytest.raises(AnyModelError, match="prompt or messages"):
        executor("ag/gemini-3.7-flash-high", {"intent": "search_and_extraction"})


def test_executor_rejects_non_https_endpoint():
    with pytest.raises(ValueError, match="HTTPS"):
        AnyModelChatExecutor("test-secret", chat_url="http://example.invalid/v1/chat/completions")


def test_executor_refuses_multi_model_selection():
    executor = AnyModelChatExecutor("test-secret")
    with pytest.raises(AnyModelError, match="exactly one model"):
        executor(("model-a", "model-b"), {"prompt": "Hi"})
