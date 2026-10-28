"""Route-level wiring: API key auth on 4 v1 routes; Telegram unaffected."""

import pytest
from fastapi.testclient import TestClient

from jamp.api import auth
from jamp.api.app import create_app

VALID_TOKEN = "jamp_sk_wiring_test"  # noqa: S105

PROTECTED = [
    ("POST", "/v1/classify"),
    ("POST", "/v1/execute"),
    ("GET", "/v1/provenance/test-trace"),
    ("POST", "/v1/verify-verdict"),
]


@pytest.fixture

def client(monkeypatch):
    monkeypatch.setattr(auth, "_lookup_by_hash", lambda _h: (42, "acme", False))
    return TestClient(create_app())


@pytest.fixture

def client_disabled_org(monkeypatch):
    monkeypatch.setattr(auth, "_lookup_by_hash", lambda _h: (42, "acme", True))
    return TestClient(create_app())


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_route_no_header_401(client, method, path):
    response = client.request(method, path, json={})
    assert response.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_route_valid_key_not_401(client, method, path):
    response = client.request(
        method,
        path,
        json={},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code != 401


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_route_disabled_org_403(client_disabled_org, method, path):
    response = client_disabled_org.request(
        method,
        path,
        json={},
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 403


def test_startup_without_secret_raises(monkeypatch):
    monkeypatch.delenv("JAMP_API_KEY_HASH_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="JAMP_API_KEY_HASH_SECRET"):
        with TestClient(create_app()):
            pass


def test_telegram_webhook_not_blocked_by_api_key(client, monkeypatch):
    """Telegram uses its own secret; it must not be intercepted by API-key auth."""
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "tg-test-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    response = client.post(
        "/v1/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "tg-test-secret"},
        json={"update_id": 1},
    )
    assert response.status_code != 401
