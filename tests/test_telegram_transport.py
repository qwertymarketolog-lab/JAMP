from unittest.mock import MagicMock

import pytest

from jamp.transport.telegram import TelegramTransport, TelegramTransportResponse


@pytest.fixture
def mock_adapter():
    return MagicMock()


def test_handle_update_execute_success(mock_adapter):
    result = MagicMock(status="EXECUTE", output="Hello from JAMP!", trace_id="trace-123")
    mock_adapter.execute_payload.return_value = result

    response = TelegramTransport(mock_adapter).handle_update(
        {"message": {"chat": {"id": 9999}, "text": "Hello bot"}}
    )

    assert response == TelegramTransportResponse(
        chat_id=9999, text="Hello from JAMP!", trace_id="trace-123"
    )
    mock_adapter.execute_payload.assert_called_once_with({"prompt": "Hello bot"})


def test_handle_update_refuse_response(mock_adapter):
    mock_adapter.execute_payload.return_value = MagicMock(
        status="REFUSE", reason="policy_violation", trace_id="trace-456"
    )

    response = TelegramTransport(mock_adapter).handle_update(
        {"message": {"chat": {"id": 8888}, "text": "Unsafe query"}}
    )

    assert response == TelegramTransportResponse(
        chat_id=8888, text="REFUSE: policy_violation", trace_id="trace-456"
    )


def test_handle_update_missing_text(mock_adapter):
    response = TelegramTransport(mock_adapter).handle_update(
        {"message": {"chat": {"id": 1234}, "photo": [{"file_id": "xyz"}]}}
    )

    assert response is None
    mock_adapter.execute_payload.assert_not_called()


def test_handle_update_missing_chat(mock_adapter):
    response = TelegramTransport(mock_adapter).handle_update(
        {"message": {"text": "Orphan message"}}
    )

    assert response is None
    mock_adapter.execute_payload.assert_not_called()


def test_handle_update_malformed_update(mock_adapter):
    transport = TelegramTransport(mock_adapter)

    assert transport.handle_update("not_a_dict") is None
    assert transport.handle_update({}) is None
    assert transport.handle_update({"message": "not_a_dict"}) is None
    mock_adapter.execute_payload.assert_not_called()


def test_handle_update_empty_text(mock_adapter):
    response = TelegramTransport(mock_adapter).handle_update(
        {"message": {"chat": {"id": 1234}, "text": "   "}}
    )

    assert response is None
    mock_adapter.execute_payload.assert_not_called()
