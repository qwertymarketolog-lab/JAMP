"""PostgreSQL persistence for tenant-scoped verification verdicts."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from psycopg2.extras import Json

from jamp.db.connection import get_connection, release_connection


def get_verdict_for_organization(
    *,
    verdict_id: str,
    organization_id: str,
) -> dict[str, Any] | None:
    """Return a verdict only when it belongs to the authenticated organization."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, status, result, created_at, code_hash
                FROM verdicts
                WHERE id = %s AND organization_id = %s
                """,
                (verdict_id, organization_id),
            )
            row = cursor.fetchone()
            if row is None:
                connection.commit()
                return None

            stored_id, status, stored_result, created_at, code_hash = row
            response = {
                "verdict_id": str(stored_id),
                "status": status,
                "result": _as_dict(stored_result),
                "evidence": _read_evidence(cursor, str(stored_id)),
                "created_at": created_at.isoformat(),
                "code_hash": code_hash.strip(),
            }
        connection.commit()
        return response
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)


def list_verdicts_for_organization(
    *,
    organization_id: str,
    limit: int,
    offset: int,
    status: str | None = None,
) -> dict[str, Any]:
    """Return paginated verdict cards scoped in SQL to one organization."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM verdicts
                WHERE organization_id = %s
                  AND (%s IS NULL OR status = %s)
                """,
                (organization_id, status, status),
            )
            total = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT id, status, result, created_at, code_hash
                FROM verdicts
                WHERE organization_id = %s
                  AND (%s IS NULL OR status = %s)
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (organization_id, status, status, limit, offset),
            )
            items = []
            for verdict_id, verdict_status, result, created_at, code_hash in cursor.fetchall():
                stored_result = _as_dict(result)
                items.append(
                    {
                        "verdict_id": str(verdict_id),
                        "status": verdict_status,
                        "package": stored_result.get("package"),
                        "created_at": created_at.isoformat(),
                        "code_hash": code_hash.strip(),
                    }
                )
        connection.commit()
        return {"items": items, "limit": limit, "offset": offset, "total": total}
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)


def get_verdict_graph_for_organization(
    *,
    verdict_id: str,
    organization_id: str,
) -> dict[str, Any] | None:
    """Project persisted evidence rows and their FK relationship to one verdict."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    v.id, v.status, v.result, v.created_at, v.code_hash,
                    e.id, e.sequence_no, e.evidence_type, e.payload,
                    e.payload_hash, e.created_at
                FROM verdicts AS v
                LEFT JOIN evidence_chain AS e ON e.verdict_id = v.id
                WHERE v.id = %s AND v.organization_id = %s
                ORDER BY e.sequence_no
                """,
                (verdict_id, organization_id),
            )
            rows = cursor.fetchall()
            if not rows:
                connection.commit()
                return None

            first = rows[0]
            stored_result = _as_dict(first[2])
            verdict_node_id = f"verdict:{first[0]}"
            nodes = [
                {
                    "id": verdict_node_id,
                    "type": "verdict",
                    "status": first[1],
                    "package": stored_result.get("package"),
                    "created_at": first[3].isoformat(),
                    "code_hash": first[4].strip(),
                }
            ]
            edges = []
            for row in rows:
                evidence_id = row[5]
                if evidence_id is None:
                    continue
                node_id = f"evidence:{evidence_id}"
                nodes.append(
                    {
                        "id": node_id,
                        "type": "evidence",
                        "sequence_no": row[6],
                        "evidence_type": row[7],
                        "payload": _as_dict(row[8]),
                        "payload_hash": row[9].strip(),
                        "created_at": row[10].isoformat(),
                    }
                )
                edges.append(
                    {
                        "id": f"{node_id}->belongs_to->{verdict_node_id}",
                        "source": node_id,
                        "target": verdict_node_id,
                        "relation": "belongs_to",
                    }
                )
        connection.commit()
        return {"nodes": nodes, "edges": edges}
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)


def get_verdict_stats_for_organization(*, organization_id: str) -> dict[str, Any]:
    """Count persisted verdict rows, with explicit all-time denominator semantics."""
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    COUNT(*) FILTER (WHERE status = 'CLEAN'),
                    COUNT(*) FILTER (WHERE status = 'SUSPICIOUS'),
                    COUNT(*) FILTER (WHERE status = 'HALLUCINATION_CAUGHT'),
                    COUNT(*) FILTER (WHERE status = 'INCONCLUSIVE'),
                    COUNT(*) FILTER (WHERE status = 'INTEGRITY_VIOLATED')
                FROM verdicts
                WHERE organization_id = %s
                """,
                (organization_id,),
            )
            row = cursor.fetchone()
        connection.commit()
        total, clean, suspicious, hallucinations, inconclusive, integrity_violated = row
        return {
            "total_checks": total,
            "hallucinations_caught": hallucinations,
            "inconclusive": inconclusive,
            "status_counts": {
                "CLEAN": clean,
                "SUSPICIOUS": suspicious,
                "HALLUCINATION_CAUGHT": hallucinations,
                "INCONCLUSIVE": inconclusive,
                "INTEGRITY_VIOLATED": integrity_violated,
            },
            "time_window": "all_time",
            "denominator": "persisted_verdict_rows (one row per idempotent verification)",
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)


class IdempotencyConflict(ValueError):
    """An idempotency key was reused for a different request."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, dict):
            return decoded
    raise ValueError("stored JSON value is not an object")


def _read_evidence(cursor: Any, verdict_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT sequence_no, evidence_type, payload, payload_hash, created_at
        FROM evidence_chain
        WHERE verdict_id = %s
        ORDER BY sequence_no
        """,
        (verdict_id,),
    )
    return [
        {
            "sequence_no": row[0],
            "evidence_type": row[1],
            "payload": _as_dict(row[2]),
            "payload_hash": row[3].strip(),
            "created_at": row[4].isoformat(),
        }
        for row in cursor.fetchall()
    ]


def persist_or_get_verdict(
    *,
    organization_id: str,
    idempotency_key: str,
    request_hash: str,
    code_hash: str,
    result: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Atomically persist verdict/evidence or return the original idempotent result.

    Verification runs before this transaction. Concurrent retries may repeat
    the external check, but an advisory transaction lock prevents duplicate
    persisted verdicts for the same tenant/key pair.
    """
    allowed_statuses = {
        "CLEAN",
        "SUSPICIOUS",
        "HALLUCINATION_CAUGHT",
        "INCONCLUSIVE",
        "INTEGRITY_VIOLATED",
    }
    if result.get("status") not in allowed_statuses:
        raise ValueError("unsupported verification status")
    if len(request_hash) != 64 or len(code_hash) != 64:
        raise ValueError("request and code hashes must be SHA-256 digests")

    lock_digest = hashlib.sha256(
        (organization_id + "\0" + idempotency_key).encode("utf-8")
    ).digest()
    lock_id = int.from_bytes(lock_digest[:8], byteorder="big", signed=True)
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            cursor.execute(
                """
                SELECT id, request_hash, result, created_at
                FROM verdicts
                WHERE organization_id = %s AND idempotency_key = %s
                """,
                (organization_id, idempotency_key),
            )
            existing = cursor.fetchone()
            if existing is not None:
                verdict_id, stored_hash, stored_result, created_at = existing
                stored_payload = _as_dict(stored_result)
                if stored_hash.strip() != request_hash:
                    raise IdempotencyConflict
                response = {
                    "verdict_id": str(verdict_id),
                    "status": stored_payload["status"],
                    "result": stored_payload,
                    "evidence": _read_evidence(cursor, str(verdict_id)),
                    "created_at": created_at.isoformat(),
                    "code_hash": code_hash,
                }
                connection.commit()
                return response, False

            verdict_id = str(uuid.uuid4())
            created_at = datetime.now(UTC)
            cursor.execute(
                """
                INSERT INTO verdicts (
                    id, organization_id, idempotency_key, request_hash,
                    code_hash, status, sample_id, result, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    verdict_id,
                    organization_id,
                    idempotency_key,
                    request_hash,
                    code_hash,
                    result["status"],
                    result.get("sample_id"),
                    Json(result),
                    created_at,
                ),
            )
            evidence_items = [
                (evidence_type, payload)
                for evidence_type, payload in (
                    ("provenance", result.get("provenance")),
                    ("signature", result.get("signature")),
                )
                if isinstance(payload, dict)
            ]
            evidence_response = []
            for sequence_no, (evidence_type, payload) in enumerate(evidence_items):
                payload_hash = _payload_hash(payload)
                cursor.execute(
                    """
                    INSERT INTO evidence_chain (
                        id, verdict_id, sequence_no, evidence_type, payload, payload_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        verdict_id,
                        sequence_no,
                        evidence_type,
                        Json(payload),
                        payload_hash,
                    ),
                )
                evidence_response.append(
                    {
                        "sequence_no": sequence_no,
                        "evidence_type": evidence_type,
                        "payload": payload,
                        "payload_hash": payload_hash,
                        "created_at": created_at.isoformat(),
                    }
                )
        connection.commit()
        return (
            {
                "verdict_id": verdict_id,
                "status": result["status"],
                "result": result,
                "evidence": evidence_response,
                "created_at": created_at.isoformat(),
                "code_hash": code_hash,
            },
            True,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)
