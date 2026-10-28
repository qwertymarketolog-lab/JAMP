from __future__ import annotations

import logging

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from jamp.api import auth

TEST_HMAC_SECRET = "test-hmac-secret-not-for-production"  # noqa: S105
VALID_TOKEN = "jamp_sk_test_token_abc123"  # noqa: S105


@pytest.fixture(autouse=True)
def _hmac_env(monkeypatch):
    monkeypatch.setenv(auth._ENV_SECRET, TEST_HMAC_SECRET)


def _build_app(calls: list[str]) -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def handler(ctx: auth.OrganizationContext = Depends(auth.require_api_key)):
        calls.append("called")
        return {"org_id": ctx.org_id, "org_name": ctx.org_name}

    return app


def _lookup_returns(row):
    def _fake(_hash: str):
        return row
    return _fake


def _lookup_raises(_hash: str):
    raise RuntimeError("db down")


# --- hash_api_key ---

def test_hash_api_key_prefix_and_length():
    h = auth.hash_api_key("token")
    assert h.startswith("v1:")
    int(h[len("v1:"):], 16)
    assert len(h) == len("v1:") + 64


def test_hash_api_key_depends_on_secret(monkeypatch):
    h1 = auth.hash_api_key("token")
    monkeypatch.setenv(auth._ENV_SECRET, "different-secret")
    h2 = auth.hash_api_key("token")
    assert h1 != h2


def test_hash_api_key_empty_token_raises():
    with pytest.raises(ValueError):
        auth.hash_api_key("")


# --- verify_auth_config ---

def test_verify_auth_config_missing_secret_raises(monkeypatch):
    monkeypatch.delenv(auth._ENV_SECRET, raising=False)
    with pytest.raises(RuntimeError):
        auth.verify_auth_config()


def test_verify_auth_config_with_secret_ok():
    auth.verify_auth_config()


# --- _parse_bearer ---

@pytest.mark.parametrize("value", [None, "", "Bearer", "Bearer ", "bearer tok", "Token abc"])
def test_parse_bearer_invalid(value):
    with pytest.raises(HTTPException) as exc:
        auth._parse_bearer(value)
    assert exc.value.status_code == 401


def test_parse_bearer_valid():
    assert auth._parse_bearer("Bearer abc") == "abc"


# --- require_api_key ---

def test_no_header_401_handler_not_called(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(auth, "_lookup_by_hash", _lookup_returns((1, "org", False)))
    r = TestClient(_build_app(calls)).get("/protected")
    assert r.status_code == 401
    assert calls == []


def test_wrong_key_401_handler_not_called(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(auth, "_lookup_by_hash", _lookup_returns(None))
    r = TestClient(_build_app(calls)).get(
        "/protected", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert r.status_code == 401
    assert calls == []


def test_valid_key_200_handler_called(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(auth, "_lookup_by_hash", _lookup_returns((42, "acme", False)))
    r = TestClient(_build_app(calls)).get(
        "/protected", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert r.status_code == 200
    assert calls == ["called"]
    assert r.json() == {"org_id": 42, "org_name": "acme"}


def test_disabled_org_403_handler_not_called(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(auth, "_lookup_by_hash", _lookup_returns((42, "acme", True)))
    r = TestClient(_build_app(calls)).get(
        "/protected", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert r.status_code == 403
    assert calls == []


def test_db_error_503_not_401_handler_not_called(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(auth, "_lookup_by_hash", _lookup_raises)
    r = TestClient(_build_app(calls)).get(
        "/protected", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert r.status_code == 503
    assert calls == []


def test_default_stub_fails_closed_503():
    # no monkeypatch → NotImplementedError → 503, never 200
    calls: list[str] = []
    r = TestClient(_build_app(calls)).get(
        "/protected", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert r.status_code == 503
    assert calls == []


# --- log hygiene ---

def test_secret_and_token_not_logged(monkeypatch, caplog):
    monkeypatch.setattr(auth, "_lookup_by_hash", _lookup_returns(None))
    with caplog.at_level(logging.DEBUG):
        TestClient(_build_app([])).get(
            "/protected", headers={"Authorization": f"Bearer {VALID_TOKEN}"}
        )
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert TEST_HMAC_SECRET not in blob
    assert VALID_TOKEN not in blob
