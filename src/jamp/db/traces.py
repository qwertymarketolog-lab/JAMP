"""Organization-scoped audit trace persistence.

All read and write operations require explicit organization_id.
No function accepts trace_id alone — this prevents cross-tenant leak
at the API surface, not only at the SQL level.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any


class OrganizationMismatchError(RuntimeError):
    """Raised when a write attempt targets an organization_id that does not exist."""


def insert_trace(
    conn: Any,
    *,
    organization_id: str,
    trace_id: str,
    payload: dict[str, Any],
) -> str:
    """Insert a trace row scoped to organization_id. Returns row id.

    Raises OrganizationMismatchError on FK violation (unknown organization).
    Raises psycopg2.errors.UniqueViolation on duplicate (organization_id, trace_id).
    """
    import psycopg2

    row_id = str(uuid.uuid4())
    created_at = datetime.now(UTC)
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO audit_traces (id, organization_id, trace_id, payload, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (row_id, organization_id, trace_id, json.dumps(payload), created_at),
            )
        except psycopg2.errors.ForeignKeyViolation:
            conn.rollback()
            raise OrganizationMismatchError(
                f"organization_id {organization_id!r} does not exist"
            ) from None
    conn.commit()
    return row_id


def fetch_trace_for_organization(
    conn: Any,
    *,
    organization_id: str,
    trace_id: str,
) -> dict[str, Any] | None:
    """Fetch a single trace scoped to organization_id.

    Returns None if the trace_id exists only under a different organization,
    or does not exist at all. Never returns a row from another organization.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT payload
            FROM audit_traces
            WHERE organization_id = %s AND trace_id = %s
            """,
            (organization_id, trace_id),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])
