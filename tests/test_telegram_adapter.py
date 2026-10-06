from unittest.mock import Mock

from jamp.client.adapter import AdapterResult
from jamp.client.telegram import TelegramBotAdapter


def test_telegram_execute_delegates_to_p25_and_renders_output():
    client = Mock()
    client.execute_payload.return_value = AdapterResult(
        status="EXECUTE",
        trace_id="trace_exec",
        selected_model="model_01",
        output="search result",
    )

    result = TelegramBotAdapter(client).handle_update(
        {"message": {"chat": {"id": 42}, "text": "find product"}}
    )

    client.execute_payload.assert_called_once_with({"prompt": "find product"})
    assert result is not None
    assert result.chat_id == 42
    assert result.text == "search result"
    assert result.trace_id == "trace_exec"


def test_telegram_refuse_renders_reason_and_trace_id():
    client = Mock()
    client.execute_payload.return_value = AdapterResult(
        status="REFUSE",
        trace_id="trace_refuse",
        reason="FAIL_CLOSED_ZERO_QUALIFIED_MODELS",
    )

    result = TelegramBotAdapter(client).handle_update(
        {"message": {"chat": {"id": 7}, "text": "blocked request"}}
    )

    client.execute_payload.assert_called_once_with({"prompt": "blocked request"})
    assert result is not None
    assert result.chat_id == 7
    assert result.text == "REFUSE: FAIL_CLOSED_ZERO_QUALIFIED_MODELS"
    assert result.trace_id == "trace_refuse"


def test_telegram_update_without_text_does_not_call_runtime():
    client = Mock()

    result = TelegramBotAdapter(client).handle_update(
        {"message": {"chat": {"id": 42}}}
    )

    client.execute_payload.assert_not_called()
    assert result is None
