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
        model_id_map={"am/nemotron-3-super-120b-a12b": "nvidia/nemotron-3-super-120b-a12b"},
        opener=fake_open,
    )
    result = executor("am/nemotron-3-super-120b-a12b", {"prompt": "Reply with OK"})

    assert seen["body"]["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result["requested_model_id"] == "am/nemotron-3-super-120b-a12b"
    assert result["provider_requested_model_id"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result["provider_model_id"] == "nvidia/nemotron-3-super-120b-a12b"
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
    assert executor._crosswalk_digest == "sha256:local-model-id-map"


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
    assert bad_secret.status_code == 401
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


@pytest.mark.parametrize("command", ["/search", "/tools"])
def test_telegram_webhook_sends_hint_for_command_without_prompt(monkeypatch, tmp_path, command):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    sent = []
    monkeypatch.setattr(
        app_module,
        "_send_telegram_message",
        lambda token, chat_id, text: sent.append((token, chat_id, text)),
    )
    client = TestClient(
        create_app(
            executor=lambda model, payload: pytest.fail("promptless command must not execute"),
            telegram_update_db_path=tmp_path / "telegram-updates.sqlite3",
        )
    )
    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={"update_id": 900, "message": {"chat": {"id": 42}, "text": command}},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "HINT_SENT"}
    assert len(sent) == 1
    assert sent[0][0:2] == ("bot-token", 42)
    assert "Формат: /search <вопрос>" in sent[0][2]
    assert "Или: /tools <задача>" in sent[0][2]


def test_telegram_webhook_promptless_duplicate_does_not_resend_hint(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    sent = []
    calls = []
    monkeypatch.setattr(
        app_module,
        "_send_telegram_message",
        lambda token, chat_id, text: sent.append(text),
    )
    database_path = tmp_path / "telegram-updates.sqlite3"
    client = TestClient(
        create_app(
            executor=lambda model, payload: calls.append(payload) or {"content": "unexpected"},
            telegram_update_db_path=database_path,
        )
    )
    headers = {"X-Telegram-Bot-Api-Secret-Token": "configured-secret"}
    update = {
        "update_id": 910,
        "message": {"chat": {"id": 42}, "text": "/search"},
    }

    first = client.post("/v1/telegram/webhook", headers=headers, json=update)
    second = client.post("/v1/telegram/webhook", headers=headers, json=update)

    assert first.status_code == 200
    assert first.json() == {"status": "HINT_SENT"}
    assert second.status_code == 200
    assert second.json()["status"] == "DUPLICATE"
    assert len(sent) == 1
    assert calls == []


def test_telegram_webhook_ignores_unknown_command(monkeypatch, tmp_path):
    import jamp.api.app as app_module

    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    sent = []
    calls = []
    monkeypatch.setattr(
        app_module,
        "_send_telegram_message",
        lambda token, chat_id, text: sent.append(text),
    )
    client = TestClient(
        create_app(
            executor=lambda model, payload: calls.append(payload) or {"content": "unexpected"},
            telegram_update_db_path=tmp_path / "telegram-updates.sqlite3",
        )
    )
    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "configured-secret"},
        json={
            "update_id": 920,
            "message": {"chat": {"id": 42}, "text": "hello without a command"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "IGNORED", "reason": "UNKNOWN_COMMAND"}
    assert calls == []
    assert sent == []


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


def test_openrouter_empty_content_error_captures_safe_provider_diagnostics():
    from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError

    reasoning = "internal reasoning must not be persisted"
    response_body = json.dumps(
        {
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": None, "reasoning": reasoning},
                }
            ],
            "usage": {"completion_tokens": 20},
        }
    ).encode()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return response_body

    executor = OpenRouterChatExecutor(
        "test-secret",
        max_tokens=20,
        opener=lambda request, timeout: Response(),
    )
    with pytest.raises(OpenRouterError, match="no text content") as caught:
        executor("nvidia/nemotron-3-super-120b-a12b", {"prompt": "Reply HELLO"})

    assert caught.value.diagnostics == {
        "finish_reason": "length",
        "usage": {"completion_tokens": 20},
        "content_len": 0,
        "reasoning_len": len(reasoning),
        "requested_max_tokens": 20,
        "model": "nvidia/nemotron-3-super-120b-a12b",
    }
    assert reasoning not in repr(caught.value.diagnostics)
    assert "test-secret" not in repr(caught.value.diagnostics)


def test_execute_persists_provider_diagnostics_on_empty_content_refusal(monkeypatch):
    import jamp.api.app as app_module
    from jamp.provider.openrouter import OpenRouterError

    selected_model = "am/nemotron-3-super-120b-a12b"
    diagnostics = {
        "finish_reason": "length",
        "usage": {"completion_tokens": 20},
        "content_len": 0,
        "reasoning_len": 41,
        "requested_max_tokens": 20,
        "model": "nvidia/nemotron-3-super-120b-a12b",
    }
    captured_traces = []
    original_create_trace = app_module.ProvenanceTracker.create_trace

    def capture_trace(self, *args, **kwargs):
        trace = original_create_trace(self, *args, **kwargs)
        captured_traces.append(trace)
        return trace

    monkeypatch.setattr(app_module.ProvenanceTracker, "create_trace", capture_trace)
    monkeypatch.setattr(
        app_module.ModelSelector,
        "select_model",
        lambda self, eligible, task_profile: ("EXECUTE", selected_model),
    )

    def executor(model, payload):
        assert model == selected_model
        raise OpenRouterError("OpenRouter response has no text content", diagnostics=diagnostics)

    client = TestClient(create_app(executor=executor))
    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "hello",
            "request_id": "empty-content-diagnostic-test",
        },
    )

    assert response.status_code == 502
    assert response.json()["reason"] == "PROVIDER_EXECUTION_FAILED"
    assert captured_traces
    trace = captured_traces[-1]
    assert trace["request_id"] == "empty-content-diagnostic-test"
    assert trace["refusal_details"]["reason"] == "PROVIDER_EXECUTION_FAILED"
    assert trace["refusal_details"]["provider_diagnostics"] == {
        **diagnostics,
        "selected_model": selected_model,
    }
    assert "internal reasoning" not in repr(trace)
    assert "content" not in trace["refusal_details"]["provider_diagnostics"]


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
            "crosswalk_digest": "sha256:local-model-id-map",
            "content": "hello",
            "qualification": "UNKNOWN",
        },
        evidence_status="VERIFIED",
    )

    details = trace["execution_details"]
    assert details["selected_model"] == "canonical/requested-id"
    assert details["requested_model_id"] == "canonical/requested-id"
    assert details["provider_requested_model_id"] == "provider/requested-id"
    assert details["provider_model_id"] == "provider/served-alias"
    assert details["crosswalk_digest"] == "sha256:local-model-id-map"
    assert details["provider"] == "openrouter"
    assert details["qualification"] == "UNKNOWN"
    assert "test_override" not in details
    assert "test_only" not in details
    assert "content" not in details
    assert details["output_digest"].startswith("sha256:")


def test_provenance_marks_legacy_executor_qualification_unknown():
    from jamp.runtime.provenance import ProvenanceTracker

    trace = ProvenanceTracker().create_trace(
        task_profile="search_and_extraction",
        required_caps=("C01", "C06"),
        action="EXECUTE",
        selected_model="legacy/model",
        eligible_count=1,
        output={"provider": "legacy", "content": "hello"},
    )

    details = trace["execution_details"]
    assert "test_override" not in details
    assert "test_only" not in details
    assert details["qualification"] == "UNKNOWN"


def test_execute_persists_unmapped_model_code_and_safe_provenance(monkeypatch):
    import jamp.api.app as app_module
    from jamp.provider.openrouter import OpenRouterError

    selected_model = "am/nemotron-3-super-120b-a12b"
    crosswalk_digest = "sha256:test-crosswalk-digest"
    captured_traces = []
    original_create_trace = app_module.ProvenanceTracker.create_trace

    def capture_trace(self, *args, **kwargs):
        trace = original_create_trace(self, *args, **kwargs)
        captured_traces.append(trace)
        return trace

    monkeypatch.setattr(app_module.ProvenanceTracker, "create_trace", capture_trace)
    monkeypatch.setattr(
        app_module.ModelSelector,
        "select_model",
        lambda self, eligible, task_profile: ("EXECUTE", selected_model),
    )

    def executor(model, payload):
        assert model == selected_model
        raise OpenRouterError(
            "MODEL_NOT_MAPPED",
            code="MODEL_NOT_MAPPED",
            diagnostics={
                "requested_model_id": selected_model,
                "crosswalk_digest": crosswalk_digest,
                "api_key": "must-not-be-persisted",
            },
        )

    client = TestClient(create_app(executor=executor))
    response = client.post(
        "/v1/execute",
        json={
            "intent": "search_and_extraction",
            "prompt": "hello",
            "request_id": "unmapped-model-provenance-test",
        },
    )

    assert response.status_code == 502
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == "PROVIDER_EXECUTION_FAILED"
    assert captured_traces

    trace = captured_traces[-1]
    assert trace["request_id"] == "unmapped-model-provenance-test"
    assert trace["refusal_details"]["reason"] == "PROVIDER_EXECUTION_FAILED"
    assert trace["refusal_details"]["provider_diagnostics"] == {
        "code": "MODEL_NOT_MAPPED",
        "selected_model": selected_model,
        "requested_model_id": selected_model,
        "crosswalk_digest": crosswalk_digest,
    }
    assert "must-not-be-persisted" not in repr(trace)
    assert "api_key" not in repr(trace)


def test_openrouter_executor_refuses_unmapped_jamp_internal_model():
    from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError

    executor = OpenRouterChatExecutor("test-secret", opener=lambda request, timeout: None)
    with pytest.raises(OpenRouterError, match="MODEL_NOT_MAPPED"):
        executor("am/model-without-crosswalk", {"prompt": "hello"})


def test_unverified_crosswalk_candidate_is_not_loaded_for_routing(tmp_path):
    from jamp.provider.openrouter import (
        OpenRouterChatExecutor,
        OpenRouterError,
        _load_crosswalk,
    )

    path = tmp_path / "openrouter.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "mappings": {
                    "am/nemotron-3-super-120b-a12b": {
                        "provider": "openrouter",
                        "provider_id": "nvidia/nemotron-3-super-120b-a12b",
                        "verified_against_catalog": False,
                        "catalog_check": {
                            "count": 470,
                            "exact_jamp_id_present": False,
                            "verification_basis": "name similarity, not identity",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    mappings, digest = _load_crosswalk(path)

    assert mappings == {}
    assert digest.startswith("sha256:")

    executor = OpenRouterChatExecutor(
        "test-secret",
        model_id_map=mappings,
        opener=lambda request, timeout: None,
    )
    with pytest.raises(OpenRouterError, match="MODEL_NOT_MAPPED"):
        executor("am/nemotron-3-super-120b-a12b", {"prompt": "hello"})


def test_openrouter_executor_does_not_emit_test_only_marker_for_free_route():
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
    assert result["qualification"] == "UNKNOWN"
    assert "test_only" not in result
    assert "test_override" not in result


def test_openrouter_executor_refuses_environment_crosswalk_override_in_production(monkeypatch):
    import jamp.provider.openrouter as provider_module
    from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("JAMP_ENVIRONMENT", "production")
    monkeypatch.setenv(
        "OPENROUTER_MODEL_ID_MAP",
        '{"am/nemotron-3-super-120b-a12b":"nvidia/nemotron-3-super-120b-a12b"}',
    )
    monkeypatch.setattr(
        provider_module,
        "_load_crosswalk",
        lambda: pytest.fail("production override guard must run before crosswalk loading"),
    )
    with pytest.raises(OpenRouterError, match="LOCAL_OVERRIDE_ONLY") as caught:
        OpenRouterChatExecutor.from_env()
    assert caught.value.code == "OPENROUTER_MODEL_ID_MAP_LOCAL_OVERRIDE_ONLY"


def test_openrouter_executor_marks_env_override_as_not_qualified(monkeypatch):
    from jamp.provider.openrouter import OpenRouterChatExecutor

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"test response"}}]}'

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")
    monkeypatch.setenv("JAMP_ENVIRONMENT", "local")
    monkeypatch.setenv(
        "OPENROUTER_MODEL_ID_MAP",
        '{"am/nemotron-3-super-120b-a12b":"nvidia/nemotron-3-super-120b-a12b"}',
    )
    executor = OpenRouterChatExecutor.from_env()
    assert executor is not None
    # Replace only the transport after environment configuration; no live call.
    executor._opener = lambda request, timeout: Response()

    result = executor("am/nemotron-3-super-120b-a12b", {"prompt": "hello"})

    assert result["qualification"] == "UNKNOWN"
    assert "test_override" not in result
    assert "test_only" not in result
    assert result["requested_model_id"] == "am/nemotron-3-super-120b-a12b"
    assert result["provider_requested_model_id"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result["crosswalk_digest"] == "sha256:local-test-override"


@pytest.mark.parametrize(
    ("verification_status", "details", "expected_reason"),
    [
        (
            "UNVERIFIABLE",
            {"reason": "PROVIDER_RESPONSE_ID_MISSING"},
            "PROVIDER_RESPONSE_ID_MISSING",
        ),
        ("CONTRADICTED", {"provider_model": "other/model"}, "EVIDENCE_CONTRADICTED"),
        (
            "INCONCLUSIVE",
            {"reason": "API_ERROR", "error": "TimeoutError"},
            "E2_VERIFICATION_INCONCLUSIVE",
        ),
    ],
)
def test_execute_fails_closed_when_e2_is_not_verified(
    monkeypatch, verification_status, details, expected_reason
):
    import jamp.api.app as app_module

    monkeypatch.setattr(
        app_module.ModelSelector,
        "select_model",
        lambda self, eligible, task_profile: ("EXECUTE", "provider/approved-model"),
    )
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda output: (verification_status, details),
    )
    client = TestClient(
        create_app(executor=lambda model, payload: {"provider": "openrouter", "content": "hello"})
    )

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "hello"},
    )

    assert response.status_code == 502
    assert response.json()["status"] == "REFUSE"
    assert response.json()["reason"] == expected_reason


def test_execute_verifies_configured_openrouter_even_when_output_provider_is_missing(
    monkeypatch,
):
    import jamp.api.app as app_module
    from jamp.provider.openrouter import OpenRouterChatExecutor

    class MalformedOpenRouterExecutor(OpenRouterChatExecutor):
        def __call__(self, selected_model, payload):
            return {"content": "must not pass without provider metadata"}

    monkeypatch.setattr(
        app_module.ModelSelector,
        "select_model",
        lambda self, eligible, task_profile: ("EXECUTE", "provider/approved-model"),
    )
    executor = MalformedOpenRouterExecutor("test-secret")
    client = TestClient(create_app(executor=executor))

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "hello"},
    )

    assert response.status_code == 502
    assert response.json()["reason"] == "PROVIDER_RESPONSE_ID_MISSING"


def test_execute_persists_verified_e2_details(monkeypatch):
    import jamp.api.app as app_module

    monkeypatch.setattr(
        app_module.ModelSelector,
        "select_model",
        lambda self, eligible, task_profile: ("EXECUTE", "provider/approved-model"),
    )
    monkeypatch.setattr(
        app_module,
        "verify_generation",
        lambda output: (
            "VERIFIED",
            {
                "provider_model": "provider/approved-model",
                "provider_name": "provider-node",
                "generation_id": "gen-verified",
            },
        ),
    )
    captured_traces = []
    original_create_trace = app_module.ProvenanceTracker.create_trace

    def capture_trace(self, *args, **kwargs):
        trace = original_create_trace(self, *args, **kwargs)
        captured_traces.append(trace)
        return trace

    monkeypatch.setattr(app_module.ProvenanceTracker, "create_trace", capture_trace)
    client = TestClient(
        create_app(
            executor=lambda model, payload: {
                "provider": "openrouter",
                "provider_response_id": "gen-verified",
                "provider_model_id": "provider/approved-model",
                "content": "hello",
            }
        )
    )

    response = client.post(
        "/v1/execute",
        json={"intent": "search_and_extraction", "prompt": "hello"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTE"
    details = captured_traces[-1]["execution_details"]
    assert details["evidence_status"] == "VERIFIED"
    assert details["evidence_details"] == {
        "provider_model": "provider/approved-model",
        "provider_name": "provider-node",
        "generation_id": "gen-verified",
    }
