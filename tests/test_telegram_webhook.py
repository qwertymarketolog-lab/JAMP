from unittest.mock import MagicMock

from jamp.transport.telegram import TelegramTransportResponse
from jamp.transport.telegram_webhook import TelegramWebhookAdapter


def test_webhook_forwards_valid_update():
    transport = MagicMock()
    expected = TelegramTransportResponse(
        chat_id=123, text="Hello", trace_id="trace-1"
    )
    transport.handle_update.return_value = expected

    response = TelegramWebhookAdapter(transport).handle_update(
        {"message": {"chat": {"id": 123}, "text": "Hello"}}
    )

    assert response == expected
    transport.handle_update.assert_called_once_with(
        {"message": {"chat": {"id": 123}, "text": "Hello"}}
    )


def test_webhook_preserves_refuse_response():
    transport = MagicMock()
    expected = TelegramTransportResponse(
        chat_id=123, text="REFUSE: policy_violation", trace_id="trace-2"
    )
    transport.handle_update.return_value = expected

    response = TelegramWebhookAdapter(transport).handle_update(
        {"message": {"chat": {"id": 123}, "text": "Unsafe"}}
    )

    assert response == expected


def test_webhook_fail_closed_for_malformed_update():
    transport = MagicMock()

    response = TelegramWebhookAdapter(transport).handle_update("not-a-dict")

    assert response is None
    transport.handle_update.assert_not_called()


def test_webhook_preserves_transport_rejection():
    transport = MagicMock()
    transport.handle_update.return_value = None

    response = TelegramWebhookAdapter(transport).handle_update(
        {"message": {"chat": {"id": 123}}}
    )

    assert response is None
    transport.handle_update.assert_called_once()
