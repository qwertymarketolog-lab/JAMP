import json
from concurrent.futures import ThreadPoolExecutor

import pytest
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
            return (
                b'{"id":"or-test","choices":[{"message":'
                b'{"content":"hello"}}],"usage":{"total_tokens":2}}'
            )

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
    assert seen["body"]["max_tokens"] == 256
    assert seen["body"]["reasoning"] == {"effort": "low"}
    assert result["requested_model_id"] == "provider/approved-model"
    assert result["provider"] == "openrouter"
    assert result["provider_response_id"] == "or-test"
    assert result["content"] == "hello"
    assert "provider_model_id" not in result
    assert "test-secret" not in repr(result)


def test_openrouter_executor_from_env_requires_key(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert OpenRouterChatExecutor.from_env() is None


def test_openrouter_executor_maps_jamp_model_id_to_provider_id():
    from jamp.provider.openrouter import OpenRouterChatExecutor

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return (
                b'{"model":"nvidia/nemotron-3-super-120b-a12b",'
                b'"choices":[{"message":{"content":"OK"}}]}'
            )

    def fake_open(request, timeout):
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return Response()

    executor = OpenRouterChatExecutor(
        "test-secret",
        model_id_map={
            "am/nemotron-3-super-120b-a12b": "nvidia/nemotron-3-super-120b-a12b"
        },
        opener=fake_open,
    )
    result = executor("am/nemotron-3-super-120b-a12b", {"prompt": "Reply with OK"})

    assert seen["body"]["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result["requested_model_id"] == "am/nemotron-3-super-120b-a12b"
    assert result["provider_requested_model_id"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result["provider_model_id"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result.get("test_only") is not True
    assert result["content"] == "OK"


def test_openrouter_executor_loads_model_id_map_from_env(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("JAMP_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "OPENROUTER_MODEL_ID_MAP",
        '{"am/nemotron-3-super-120b-a12b":"nvidia/nemotron-3-super-120b-a12b"}',
    )

    executor = OpenRouterChatExecutor.from_env()

    assert executor is not None
    assert executor._model_id_map == {
        "am/nemotron-3-super-120b-a12b": "nvidia/nemotron-3-super-120b-a12b"
    }


def test_openrouter_executor_rejects_invalid_model_id_map_from_env(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("JAMP_ENVIRONMENT", "test")
    monkeypatch.setenv("OPENROUTER_MODEL_ID_MAP", "not-json")

    with pytest.raises(ValueError, match="OPENROUTER_MODEL_ID_MAP"):
        OpenRouterChatExecutor.from_env()


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


def test_telegram_webhook_executes_and_returns_trace(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(app_module, "_send_telegram_message", lambda token, chat_id, text: None)
    calls = []

    def executor(model, payload):
        calls.append(payload)
        return {"content": "hello from model"}

    client = TestClient(
        create_app(
            executor=executor,
            telegram_update_db_path=tmp_path / "telegram-updates.sqlite3",
        )
    )
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

    def executor(model, payload):
        calls.append(payload)
        return {"content": "unexpected"}

    client = TestClient(create_app(executor=executor))
    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"update_id": 9, "message": {"chat": {"id": 42}, "text": "hello without a command"}},
    )
    assert response.status_code == 422
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "TELEGRAM_TASK_PROFILE_REQUIRED"
    assert calls == []


def test_telegram_webhook_duplicate_is_not_executed_again_after_restart(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(app_module, "_send_telegram_message", lambda token, chat_id, text: None)
    database_path = tmp_path / "telegram-updates.sqlite3"
    calls = []

    def executor(model, payload):
        calls.append(payload)
        return {"content": "hello from model"}

    headers = {"X-Telegram-Bot-Api-Secret-Token": "configured-secret"}
    update = {
        "update_id": 800,
        "message": {"chat": {"id": 42}, "text": "/search hello"},
    }

    first_client = TestClient(create_app(executor=executor, telegram_update_db_path=database_path))
    first = first_client.post("/v1/telegram/webhook", headers=headers, json=update)
    first_client.close()

    restarted_client = TestClient(
        create_app(executor=executor, telegram_update_db_path=database_path)
    )
    duplicate = restarted_client.post("/v1/telegram/webhook", headers=headers, json=update)

    assert first.status_code == 200
    assert first.json()["status"] == "EXECUTE"
    assert duplicate.status_code == 200
    assert duplicate.json() == {
        "status": "DUPLICATE",
        "reason": "TELEGRAM_UPDATE_ALREADY_CLAIMED",
    }
    assert len(calls) == 1


def test_telegram_update_store_claim_is_atomic_under_concurrency(tmp_path):
    from jamp.transport.telegram_updates import TelegramUpdateStore

    store = TelegramUpdateStore(tmp_path / "telegram-updates.sqlite3")

    def claim(_: int) -> bool:
        return store.claim(900)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(16)))

    assert sum(results) == 1
    assert TelegramUpdateStore(tmp_path / "telegram-updates.sqlite3").claim(900) is False


def test_telegram_webhook_fails_closed_when_update_store_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    calls = []
    client = TestClient(
        create_app(
            executor=lambda model, payload: calls.append(payload) or {"content": "unexpected"},
            telegram_update_db_path=tmp_path,
        )
    )

    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"update_id": 901, "message": {"chat": {"id": 42}, "text": "/search hello"}},
    )

    assert response.status_code == 503
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "TELEGRAM_IDEMPOTENCY_UNAVAILABLE"
    assert calls == []


def test_telegram_webhook_refuses_missing_update_id_before_execution(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    calls = []
    client = TestClient(
        create_app(
            executor=lambda model, payload: calls.append(payload) or {"content": "unexpected"},
            telegram_update_db_path=tmp_path / "telegram-updates.sqlite3",
        )
    )

    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"message": {"chat": {"id": 42}, "text": "/search hello"}},
    )

    assert response.status_code == 422
    assert response.json()["reason"] == "TELEGRAM_UPDATE_ID_REQUIRED"
    assert calls == []


def test_openrouter_executor_records_provider_model_separately_from_requested_model():
    from jamp.provider.openrouter import OpenRouterChatExecutor

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"model":"provider/served-alias","choices":[{"message":{"content":"hello"}}]}'

    executor = OpenRouterChatExecutor("test-secret", opener=lambda request, timeout: Response())
    result = executor("canonical/requested-id", {"prompt": "hello"})

    assert result["requested_model_id"] == "canonical/requested-id"
    assert result["model"] == "canonical/requested-id"
    assert result["provider_model_id"] == "provider/served-alias"


@pytest.mark.parametrize(
    "response_body",
    [
        b'{"choices":[{"message":{"content":""}}]}',
        b'{"choices":[{"message":{"content":"   "}}]}',
        b'{"choices":[{"message":{"content":null}}]}',
        b'{"choices":[{"message":{}}]}',
        b'{"choices":[{"message":{"content":""},"finish_reason":"length"}]}',
    ],
)
def test_openrouter_executor_fails_closed_when_response_has_no_text(response_body):
    from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return response_body

    executor = OpenRouterChatExecutor("test-secret", opener=lambda request, timeout: Response())
    with pytest.raises(OpenRouterError, match="no text content"):
        executor("provider/approved-model", {"prompt": "hello"})


def test_openrouter_executor_can_disable_reasoning():
    from jamp.provider.openrouter import OpenRouterChatExecutor

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"hello"}}]}'

    def fake_open(request, timeout):
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return Response()

    OpenRouterChatExecutor("test-secret", reasoning_effort=None, opener=fake_open)(
        "provider/approved-model", {"prompt": "hello"}
    )
    assert seen["body"]["max_tokens"] == 256
    assert "reasoning" not in seen["body"]


def test_openrouter_executor_validates_generation_settings():
    from jamp.provider.openrouter import OpenRouterChatExecutor

    with pytest.raises(ValueError, match="max_tokens"):
        OpenRouterChatExecutor("test-secret", max_tokens=0)
    with pytest.raises(ValueError, match="reasoning_effort"):
        OpenRouterChatExecutor("test-secret", reasoning_effort="unlimited")


def test_openrouter_executor_generation_settings_from_env(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("OPENROUTER_MAX_TOKENS", "384")
    monkeypatch.setenv("OPENROUTER_REASONING_EFFORT", "medium")
    executor = OpenRouterChatExecutor.from_env()
    assert executor is not None
    assert executor._max_tokens == 384
    assert executor._reasoning_effort == "medium"


def test_provenance_records_requested_and_provider_model_ids_separately():
    from jamp.runtime.provenance import ProvenanceTracker

    trace = ProvenanceTracker().create_trace(
        task_profile="search_and_extraction",
        required_caps=("C01", "C06"),
        action="EXECUTE",
        selected_model="canonical/requested-id",
        eligible_count=1,
        output={
            "provider": "openrouter",
            "requested_model_id": "canonical/requested-id",
            "provider_requested_model_id": "provider/requested-id",
            "provider_model_id": "provider/served-alias",
            "crosswalk_digest": "sha256:local-test-override",
            "content": "hello",
        },
    )

    details = trace["execution_details"]
    assert details["selected_model"] == "canonical/requested-id"
    assert details["requested_model_id"] == "canonical/requested-id"
    assert details["provider_requested_model_id"] == "provider/requested-id"
    assert details["provider_model_id"] == "provider/served-alias"
    assert details["crosswalk_digest"] == "sha256:local-test-override"
    assert details["provider"] == "openrouter"
    assert "content" not in details
    assert details["output_digest"].startswith("sha256:")


def test_openrouter_executor_refuses_unmapped_jamp_internal_model():
    from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError

    executor = OpenRouterChatExecutor("test-secret", opener=lambda request, timeout: None)
    with pytest.raises(OpenRouterError, match="MODEL_NOT_MAPPED"):
        executor("am/model-without-crosswalk", {"prompt": "hello"})


def test_openrouter_executor_marks_free_route_as_test_only():
    from jamp.provider.openrouter import OpenRouterChatExecutor

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"test only"}}]}'

    executor = OpenRouterChatExecutor(
        "test-secret",
        model_id_map={"am/test-model": "provider/test-model:free"},
        opener=lambda request, timeout: Response(),
    )
    result = executor("am/test-model", {"prompt": "hello"})
    assert result["test_only"] is True


def test_openrouter_executor_refuses_environment_crosswalk_override_in_production(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("JAMP_ENVIRONMENT", "production")
    monkeypatch.setenv("OPENROUTER_MODEL_ID_MAP", "{}")
    with pytest.raises(OpenRouterError, match="LOCAL_OVERRIDE_ONLY"):
        OpenRouterChatExecutor.from_env()
