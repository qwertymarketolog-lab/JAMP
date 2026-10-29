"""PostgreSQL integration for API-key auth lookup (commit 3)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from jamp.api import auth
from jamp.db import get_connection, init_schema, release_connection

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("JAMP_DATABASE_URL"),
        reason="PostgreSQL integration tests require JAMP_DATABASE_URL",
    ),
    pytest.mark.real_auth,
]


@pytest.fixture(scope="module", autouse=True)
def _schema() -> None:
    init_schema()


@pytest.fixture(autouse=True)
def _hmac_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth._ENV_SECRET, "test-hmac-secret-not-for-production")


@pytest.fixture
def org_factory() -> Iterator[Callable[..., str]]:
    created: list[str] = []

    def _make(api_key_hash: str, *, disabled: bool = False) -> str:
        org_id = str(uuid.uuid4())
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO organizations (id, name, api_key_hash, disabled, plan) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (org_id, f"test-{org_id[:8]}", api_key_hash, disabled, "free"),
                )
            conn.commit()
        finally:
            release_connection(conn)
        created.append(org_id)
        return org_id

    yield _make

    if created:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM organizations WHERE id = ANY(%s)", (created,))
            conn.commit()
        finally:
            release_connection(conn)


def test_lookup_finds_active_org(org_factory):
    api_key_hash = auth.hash_api_key("key-active")
    org_id = org_factory(api_key_hash)
    assert auth._lookup_by_hash(api_key_hash) == (
        org_id,
        f"test-{org_id[:8]}",
        False,
    )


def test_lookup_returns_none_for_unknown_hash():
    assert auth._lookup_by_hash(f"v1:{uuid.uuid4().hex}") is None


def test_disabled_org_gets_403(org_factory):
    org_factory(auth.hash_api_key("key-disabled"), disabled=True)
    app = FastAPI()

    @app.get("/protected")
    async def protected(
        ctx: Annotated[auth.OrganizationContext, Depends(auth.require_api_key)],
    ):
        return {"org_id": ctx.org_id, "org_name": ctx.org_name}

    response = TestClient(app).get("/protected", headers={"Authorization": "Bearer key-disabled"})
    assert response.status_code == 403


def test_hash_is_used_verbatim_not_plaintext(org_factory):
    token = "key-verbatim"
    api_key_hash = auth.hash_api_key(token)
    org_factory(api_key_hash)
    assert auth._lookup_by_hash(api_key_hash) is not None
    assert auth._lookup_by_hash(token) is None


def test_cross_org_isolation(org_factory):
    hash_a = auth.hash_api_key("key-a")
    hash_b = auth.hash_api_key("key-b")
    org_a = org_factory(hash_a)
    org_factory(hash_b)
    row = auth._lookup_by_hash(hash_a)
    assert row is not None and row[0] == org_a
