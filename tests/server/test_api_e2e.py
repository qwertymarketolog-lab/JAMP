"""PostgreSQL-backed HTTP E2E coverage for the C3 verification API."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from jamp.api.app import create_app
from jamp.api.auth import hash_api_key
from jamp.db import get_connection, init_schema, release_connection

pytestmark = pytest.mark.skipif(
    not os.environ.get("JAMP_DATABASE_URL"),
    reason="PostgreSQL HTTP E2E tests require JAMP_DATABASE_URL",
)

_ALLOWED_STATUSES = {
    "CLEAN",
    "SUSPICIOUS",
    "HALLUCINATION_CAUGHT",
    "INCONCLUSIVE",
    "INTEGRITY_VIOLATED",
}


@pytest.fixture
def tenant_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[tuple[str, str], tuple[str, str]]]:
    """Create two isolated tenants with API keys stored only as hashes."""
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "c4-e2e-test-hash-secret")
    init_schema()

    tenants = (
        (str(uuid.uuid4()), secrets.token_urlsafe(32), "c4-e2e-tenant-a"),
        (str(uuid.uuid4()), secrets.token_urlsafe(32), "c4-e2e-tenant-b"),
    )
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for org_id, token, name in tenants:
                cursor.execute(
                    """
                    INSERT INTO organizations (id, name, api_key_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (org_id, name, hash_api_key(token)),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)

    try:
        yield (tenants[0][0], tenants[0][1]), (tenants[1][0], tenants[1][1])
    finally:
        cleanup_connection = get_connection()
        try:
            with cleanup_connection.cursor() as cursor:
                for org_id, _, _ in tenants:
                    cursor.execute(
                        """
                        DELETE FROM evidence_chain
                        USING verdicts
                        WHERE evidence_chain.verdict_id = verdicts.id
                          AND verdicts.organization_id = %s
                        """,
                        (org_id,),
                    )
                    cursor.execute(
                        "DELETE FROM verdicts WHERE organization_id = %s",
                        (org_id,),
                    )
                    cursor.execute(
                        "DELETE FROM organizations WHERE id = %s",
                        (org_id,),
                    )
            cleanup_connection.commit()
        except Exception:
            cleanup_connection.rollback()
            raise
        finally:
            release_connection(cleanup_connection)


def _canonical_payload_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _read_persisted_verdict(
    verdict_id: str,
) -> tuple[str, str, dict[str, object], list[dict[str, object]]]:
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT organization_id, status, result
                FROM verdicts
                WHERE id = %s
                """,
                (verdict_id,),
            )
            verdict_row = cursor.fetchone()
            assert verdict_row is not None

            cursor.execute(
                """
                SELECT sequence_no, evidence_type, payload, payload_hash
                FROM evidence_chain
                WHERE verdict_id = %s
                ORDER BY sequence_no
                """,
                (verdict_id,),
            )
            evidence_rows = [
                {
                    "sequence_no": row[0],
                    "evidence_type": row[1],
                    "payload": row[2],
                    "payload_hash": row[3].strip(),
                }
                for row in cursor.fetchall()
            ]
        return (
            verdict_row[0],
            verdict_row[1],
            verdict_row[2],
            evidence_rows,
        )
    finally:
        release_connection(connection)


def test_verify_http_auth_engine_and_postgres_tenant_isolation(
    tenant_credentials: tuple[tuple[str, str], tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Exercise real route/auth/engine/persistence with only PyPI HTTP isolated.

    PyPI's HTTP boundary returns a deterministic 404, following the existing
    provenance unit-test pattern. The real check_provenance and verify_code
    orchestration still run; no route, auth, engine, or persistence result is
    replaced. A unique synthetic package name prevents dependence on a real
    package's current registry state.
    """
    from jamp.server.checks import provenance

    org_a, token_a = tenant_credentials[0]
    org_b, token_b = tenant_credentials[1]
    package_name = f"jamp_c4_missing_{uuid.uuid4().hex}"
    code_str = f"import {package_name}\n{package_name}.get_secure_data()"
    idempotency_key = f"c4-{uuid.uuid4().hex}"
    unknown_idempotency_key = f"c4-unknown-{uuid.uuid4().hex}"
    unknown_token = secrets.token_urlsafe(32)
    pypi_queries: list[str] = []

    def pypi_not_found(name: str) -> tuple[int, None]:
        pypi_queries.append(name)
        return 404, None

    monkeypatch.setattr(provenance, "fetch_pypi_json", pypi_not_found)

    app = create_app(telegram_update_db_path=tmp_path / "telegram-updates.sqlite3")
    request_body = {"code_str": code_str, "package_name": package_name}
    with TestClient(app) as client:
        response_a = client.post(
            "/v1/verify",
            json=request_body,
            headers={
                "Authorization": f"Bearer {token_a}",
                "Idempotency-Key": idempotency_key,
            },
        )
        response_b = client.post(
            "/v1/verify",
            json=request_body,
            headers={
                "Authorization": f"Bearer {token_b}",
                "Idempotency-Key": idempotency_key,
            },
        )
        unauthorized = client.post(
            "/v1/verify",
            json=request_body,
            headers={
                "Authorization": f"Bearer {unknown_token}",
                "Idempotency-Key": unknown_idempotency_key,
            },
        )

    assert response_a.status_code == 201
    assert response_b.status_code == 201
    assert unauthorized.status_code == 401
    assert pypi_queries == [package_name, package_name]

    body_a = response_a.json()
    body_b = response_b.json()
    for body in (body_a, body_b):
        assert body["status"] in _ALLOWED_STATUSES
        assert body["result"]["status"] == body["status"]
        assert body["verdict_id"]
        assert body["evidence"]

    # The expected classification is intentionally not hardcoded. It is
    # whatever the actual engine returns after the deterministic PyPI 404.
    assert body_a["status"] in {"HALLUCINATION_CAUGHT", "INCONCLUSIVE"}
    assert body_b["status"] in {"HALLUCINATION_CAUGHT", "INCONCLUSIVE"}
    assert body_a["verdict_id"] != body_b["verdict_id"]

    for expected_org_id, body in ((org_a, body_a), (org_b, body_b)):
        stored_org_id, stored_status, stored_result, stored_evidence = (
            _read_persisted_verdict(body["verdict_id"])
        )
        assert stored_org_id == expected_org_id
        assert stored_status == body["status"]
        assert stored_result == body["result"]
        assert len(stored_evidence) == len(body["evidence"])

        for stored_item, response_item in zip(
            stored_evidence, body["evidence"], strict=True
        ):
            assert stored_item["sequence_no"] == response_item["sequence_no"]
            assert stored_item["evidence_type"] == response_item["evidence_type"]
            assert stored_item["payload"] == response_item["payload"]
            expected_hash = _canonical_payload_hash(stored_item["payload"])
            assert stored_item["payload_hash"] == expected_hash
            assert response_item["payload_hash"] == expected_hash

    # The same idempotency key is unique only within a tenant. Each tenant
    # owns exactly its own row; neither request can collide with the other.
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            for expected_org_id, expected_verdict_id in (
                (org_a, body_a["verdict_id"]),
                (org_b, body_b["verdict_id"]),
            ):
                cursor.execute(
                    """
                    SELECT id::text, organization_id, idempotency_key
                    FROM verdicts
                    WHERE organization_id = %s AND idempotency_key = %s
                    """,
                    (expected_org_id, idempotency_key),
                )
                tenant_rows = cursor.fetchall()
                assert tenant_rows == [
                    (expected_verdict_id, expected_org_id, idempotency_key)
                ]
            cursor.execute(
                "SELECT COUNT(*) FROM verdicts WHERE idempotency_key = %s",
                (unknown_idempotency_key,),
            )
            assert cursor.fetchone()[0] == 0
    finally:
        release_connection(connection)

    # No GET/read endpoint exists for verdicts yet; HTTP read-path tenant
    # isolation remains NOT TESTABLE here (see DEC-001 / issue #497).
