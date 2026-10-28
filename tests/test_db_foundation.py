"""Integration tests for the opt-in PostgreSQL database foundation."""

import os
import uuid
from collections.abc import Iterator

import pytest
from psycopg2.extras import Json

from jamp.db import get_connection, init_schema, release_connection
from jamp.db.traces import fetch_trace_for_organization, insert_trace


@pytest.fixture
def db_connection() -> Iterator[object]:
    if not os.environ.get("JAMP_DATABASE_URL"):
        pytest.skip("PostgreSQL integration tests require JAMP_DATABASE_URL")

    init_schema()
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM audit_traces")
            cursor.execute("DELETE FROM organizations")
        connection.commit()
        yield connection
    finally:
        connection.rollback()
        release_connection(connection)


def _insert_organization(connection: object, *, name: str, key_hash: str) -> str:
    organization_id = str(uuid.uuid4())
    with connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            INSERT INTO organizations (id, name, api_key_hash, plan)
            VALUES (%s, %s, %s, %s)
            """,
            (organization_id, name, key_hash, "free"),
        )
    connection.commit()  # type: ignore[attr-defined]
    return organization_id


def test_init_schema_idempotent(db_connection: object) -> None:
    init_schema()
    init_schema()


def test_organization_roundtrip(db_connection: object) -> None:
    key_hash = "a" * 64
    organization_id = _insert_organization(db_connection, name="roundtrip", key_hash=key_hash)
    with db_connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            "SELECT id, name, api_key_hash, plan, disabled "
            "FROM organizations WHERE api_key_hash = %s",
            (key_hash,),
        )
        row = cursor.fetchone()
    assert row == (organization_id, "roundtrip", key_hash, "free", False)


def test_trace_insert_and_fetch(db_connection: object) -> None:
    organization_id = _insert_organization(db_connection, name="trace-owner", key_hash="b" * 64)
    payload = {"trace_id": "trace_roundtrip", "verdict": "OBSERVED"}
    with db_connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            INSERT INTO audit_traces (id, organization_id, trace_id, payload)
            VALUES (%s, %s, %s, %s)
            """,
            (str(uuid.uuid4()), organization_id, "trace_roundtrip", Json(payload)),
        )
        cursor.execute(
            """
            SELECT organization_id, trace_id, payload
            FROM audit_traces WHERE organization_id = %s AND trace_id = %s
            """,
            (organization_id, "trace_roundtrip"),
        )
        row = cursor.fetchone()
    assert row == (organization_id, "trace_roundtrip", payload)


def test_two_orgs_same_trace_id(db_connection: object) -> None:
    first_org = _insert_organization(db_connection, name="first", key_hash="c" * 64)
    second_org = _insert_organization(db_connection, name="second", key_hash="d" * 64)
    with db_connection.cursor() as cursor:  # type: ignore[attr-defined]
        for organization_id, payload_value in (
            (first_org, "first-payload"),
            (second_org, "second-payload"),
        ):
            cursor.execute(
                """
                INSERT INTO audit_traces (id, organization_id, trace_id, payload)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    organization_id,
                    "trace_shared",
                    Json({"owner": payload_value}),
                ),
            )
        cursor.execute(
            """
            SELECT organization_id, payload
            FROM audit_traces
            WHERE trace_id = %s
            ORDER BY organization_id
            """,
            ("trace_shared",),
        )
        rows = cursor.fetchall()
    assert len(rows) == 2
    assert {row[0] for row in rows} == {first_org, second_org}
    payload_by_org = {row[0]: row[1]["owner"] for row in rows}
    assert payload_by_org == {first_org: "first-payload", second_org: "second-payload"}


def test_organization_cascade_delete(db_connection: object) -> None:
    organization_id = _insert_organization(db_connection, name="cascade", key_hash="e" * 64)
    with db_connection.cursor() as cursor:  # type: ignore[attr-defined]
        cursor.execute(
            """
            INSERT INTO audit_traces (id, organization_id, trace_id, payload)
            VALUES (%s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                organization_id,
                "trace_cascade",
                Json({"trace_id": "trace_cascade"}),
            ),
        )
        cursor.execute("DELETE FROM organizations WHERE id = %s", (organization_id,))
        cursor.execute(
            "SELECT COUNT(*) FROM audit_traces WHERE organization_id = %s",
            (organization_id,),
        )
        remaining = cursor.fetchone()[0]
    assert remaining == 0


def test_fetch_trace_isolated_between_organizations(db_connection: object) -> None:
    org_a = _insert_organization(db_connection, name="Org A", key_hash="f" * 64)
    org_b = _insert_organization(db_connection, name="Org B", key_hash="g" * 64)

    insert_trace(
        db_connection,
        organization_id=org_a,
        trace_id="trace_shared",
        payload={"who": "A", "value": 1},
    )
    insert_trace(
        db_connection,
        organization_id=org_b,
        trace_id="trace_shared",
        payload={"who": "B", "value": 2},
    )

    got_a = fetch_trace_for_organization(
        db_connection, organization_id=org_a, trace_id="trace_shared"
    )
    got_b = fetch_trace_for_organization(
        db_connection, organization_id=org_b, trace_id="trace_shared"
    )

    assert got_a == {"who": "A", "value": 1}
    assert got_b == {"who": "B", "value": 2}
    assert got_a != got_b


def test_fetch_trace_returns_none_for_wrong_organization(db_connection: object) -> None:
    org_a = _insert_organization(db_connection, name="Org A", key_hash="h" * 64)
    org_b = _insert_organization(db_connection, name="Org B", key_hash="i" * 64)

    insert_trace(
        db_connection,
        organization_id=org_a,
        trace_id="trace_only_A",
        payload={"sensitive": "only-A"},
    )

    got = fetch_trace_for_organization(
        db_connection, organization_id=org_b, trace_id="trace_only_A"
    )
    assert got is None
