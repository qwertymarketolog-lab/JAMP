from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jamp.transport.telegram import TelegramTransport
from jamp.transport.webhook import create_telegram_webhook_router


SECRET = "test-secret"


def make_client():
    transport = Mock(spec=TelegramTransport)
    app = FastAPI()
    app.include_router(create_telegram_webhook_router(transport, SECRET))
    return TestClient(app), transport


def test_webhook_valid_payload():
    client, transport = make_client()

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        json={"update_id": 1},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    transport.handle_update.assert_called_once_with({"update_id": 1})


def test_webhook_invalid_secret_token():
    client, transport = make_client()

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        json={"update_id": 1},
    )

    assert response.status_code == 403
    transport.handle_update.assert_not_called()


def test_webhook_missing_secret_token():
    client, transport = make_client()

    response = client.post("/webhook/telegram", json={"update_id": 1})

    assert response.status_code == 403
    transport.handle_update.assert_not_called()


def test_webhook_malformed_json():
    client, transport = make_client()

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        content=b"{not-json",
    )

    assert response.status_code == 400
    transport.handle_update.assert_not_called()


def test_webhook_transport_returns_none():
    client, transport = make_client()
    transport.handle_update.return_value = None

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
        json={"message": {"chat": {"id": 42}}},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    transport.handle_update.assert_called_once_with(
        {"message": {"chat": {"id": 42}}}
    )
