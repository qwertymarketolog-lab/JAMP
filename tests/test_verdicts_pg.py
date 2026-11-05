"""PostgreSQL integration tests for C3 verdict persistence."""

from __future__ import annotations

from collections.abc import Iterator
import os
import uuid

import psycopg2
import pytest

from jamp.db import get_connection, init_schema, release_connection
from jamp.db.verdicts import IdempotencyConflict, persist_or_get_verdict


pytestmark = pytest.mark.skipif(
    not os.environ.get("JAMP_DATABASE_URL"),
    reason="PostgreSQL integration tests require JAMP_DATABASE_URL",
)


@pytest.fixture
def organization_id() -> Iterator[str]:
    init_schema()
    org_id = str(uuid.uuid4())
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO organizations (id, name, api_key_hash) VALUES (%s, %s, %s)",
                (org_id, "c3-test", f"c3:{org_id}"),
            )
        connection.commit()
        yield org_id
    finally:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM evidence_chain USING verdicts
                WHERE evidence_chain.verdict_id = verdicts.id
                  AND verdicts.organization_id = %s
                """,
                (org_id,),
            )
            cursor.execute(
                "DELETE FROM verdicts WHERE organization_id = %s", (org_id,)
            )
            cursor.execute("DELETE FROM organizations WHERE id = %s", (org_id,))
        connection.commit()
        release_connection(connection)


def _result(status: str = "CLEAN") -> dict:
    return {
        "status": status,
        "package": "sample-package",
        "sample_id": "sample-1",
        "provenance": {"status": "TRUSTED", "source": "test"},
        "signature": {"status": "EXISTS", "wheel": "sample.whl"},
    }


def test_verdict_and_evidence_persist_together(organization_id: str) -> None:
    stored, created = persist_or_get_verdict(
        organization_id=organization_id,
        idempotency_key="k1",
        request_hash="a" * 64,
        code_hash="b" * 64,
        result=_result(),
    )
    assert created is True
    assert stored["status"] == "CLEAN"
    assert [item["evidence_type"] for item in stored["evidence"]] == [
        "provenance",
        "signature",
    ]


def test_replay_returns_original_verdict(organization_id: str) -> None:
    first, created = persist_or_get_verdict(
        organization_id=organization_id,
        idempotency_key="k2",
        request_hash="c" * 64,
        code_hash="d" * 64,
        result=_result(),
    )
    second, replayed = persist_or_get_verdict(
        organization_id=organization_id,
        idempotency_key="k2",
        request_hash="c" * 64,
        code_hash="d" * 64,
        result=_result("INCONCLUSIVE"),
    )
    assert created is True
    assert replayed is False
    assert first["verdict_id"] == second["verdict_id"]
    assert first["result"] == second["result"]


def test_reused_key_with_different_request_conflicts(organization_id: str) -> None:
    persist_or_get_verdict(
        organization_id=organization_id,
        idempotency_key="k3",
        request_hash="e" * 64,
        code_hash="f" * 64,
        result=_result(),
    )
    with pytest.raises(IdempotencyConflict):
        persist_or_get_verdict(
            organization_id=organization_id,
            idempotency_key="k3",
            request_hash="1" * 64,
            code_hash="2" * 64,
            result=_result(),
        )


def test_evidence_hash_is_canonical() -> None:
    from jamp.db.verdicts import _payload_hash

    assert _payload_hash({"b": 2, "a": 1}) == _payload_hash({"a": 1, "b": 2})


def test_verdict_restricts_organization_deletion(organization_id: str) -> None:
    persist_or_get_verdict(
        organization_id=organization_id,
        idempotency_key="k4",
        request_hash="3" * 64,
        code_hash="4" * 64,
        result=_result(),
    )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                cursor.execute(
                    "DELETE FROM organizations WHERE id = %s", (organization_id,)
                )
            connection.rollback()
    finally:
        release_connection(connection)
