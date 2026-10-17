
import json

from fastapi.testclient import TestClient

from jamp.api import create_app


def test_openrouter_executor_uses_selected_model_and_does_not_expose_key():
    from jamp.provider.openrouter import OpenRouterChatExecutor

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"id":"or-test","choices":[{"message":{"content":"hello"}}],"usage":{"total_tokens":2}}'

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return Response()

    executor = OpenRouterChatExecutor("test-secret", opener=fake_open)
    result = executor("provider/approved-model", {"prompt": "hello"})

    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["auth"] == "Bearer test-secret"
    assert seen["body"]["model"] == "provider/approved-model"
    assert result["provider"] == "openrouter"
    assert result["provider_response_id"] == "or-test"
    assert result["content"] == "hello"
    assert "test-secret" not in repr(result)


def test_openrouter_executor_from_env_requires_key(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert OpenRouterChatExecutor.from_env() is None


def test_telegram_webhook_refuses_when_not_configured(monkeypatch):
    for key in ("TELEGRAM_WEBHOOK_SECRET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(key, raising=False)
    response = TestClient(create_app(executor=lambda model, payload: {"content": "hello"})).post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret"},
        json={"update_id": 1, "message": {"chat": {"id": 42}, "text": "hello"}},
    )
    assert response.status_code == 503
    assert response.json()["reason"] == "TELEGRAM_NOT_CONFIGURED"


def test_telegram_webhook_checks_secret_and_chat_before_execution(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    calls = []
    client = TestClient(
        create_app(executor=lambda model, payload: calls.append(payload) or {"content": "hello"})
    )
    bad_secret = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"message": {"chat": {"id": 42}, "text": "hello"}},
    )
    bad_chat = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"message": {"chat": {"id": 99}, "text": "hello"}},
    )
    assert bad_secret.status_code == 403
    assert bad_chat.status_code == 403
    assert calls == []


def test_telegram_webhook_executes_and_returns_trace(monkeypatch):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(app_module, "_send_telegram_message", lambda token, chat_id, text: None)
    calls = []

    def executor(model, payload):
        calls.append(payload)
        return {"content": "hello from model"}

    client = TestClient(create_app(executor=executor))
    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"update_id": 8, "message": {"chat": {"id": 42}, "text": "/search hello"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTE"
    assert response.json()["trace_id"]
    assert calls[0]["intent"] == "search_and_extraction"
    assert calls[0]["prompt"] == "hello"


def test_telegram_webhook_refuses_undeclared_task_profile(monkeypatch):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(app_module, "_send_telegram_message", lambda token, chat_id, text: None)
    calls = []
    client = TestClient(
        create_app(executor=lambda model, payload: calls.append(payload) or {"content": "unexpected"})
    )
    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"update_id": 9, "message": {"chat": {"id": 42}, "text": "hello without a command"}},
    )
    assert response.status_code == 422
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "TELEGRAM_TASK_PROFILE_REQUIRED"
    assert calls == []
