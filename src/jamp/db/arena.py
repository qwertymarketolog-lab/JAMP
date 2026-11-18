"""Tenant-scoped persistence and idempotency for Arena executions."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from psycopg2.extras import Json

from jamp.db.connection import get_connection, release_connection


class ArenaIdempotencyConflict(ValueError):
    """An idempotency key was reused for a different Arena request."""


def _request_hash(prompt: str, models: list[str]) -> str:
    canonical = json.dumps(
        {"prompt": prompt, "models": models},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return decoded
    raise ValueError("stored Arena results are not a JSON array")


def reserve_arena_run(
    *,
    organization_id: str,
    idempotency_key: str,
    prompt: str,
    models: list[str],
) -> tuple[dict[str, Any], bool]:
    """Reserve an idempotency key before provider execution.

    A duplicate terminal request returns its original result. A duplicate still
    marked RUNNING is never executed a second time and is returned as RUNNING.
    """
    request_hash = _request_hash(prompt, models)
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
                SELECT id, request_hash, status, results
                FROM arena_runs
                WHERE organization_id = %s AND idempotency_key = %s
                """,
                (organization_id, idempotency_key),
            )
            existing = cursor.fetchone()
            if existing is not None:
                run_id, stored_hash, status, stored_results = existing
                if stored_hash.strip() != request_hash:
                    raise ArenaIdempotencyConflict
                response = {
                    "run_id": str(run_id),
                    "status": status,
                    "results": _as_list(stored_results),
                }
                connection.commit()
                return response, False

            run_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO arena_runs (
                    id, organization_id, idempotency_key, request_hash,
                    prompt, status, results
                )
                VALUES (%s, %s, %s, %s, %s, 'RUNNING', %s)
                """,
                (
                    run_id,
                    organization_id,
                    idempotency_key,
                    request_hash,
                    prompt,
                    Json([]),
                ),
            )
        connection.commit()
        return {"run_id": run_id, "status": "RUNNING", "results": []}, True
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)


def complete_arena_run(
    *,
    organization_id: str,
    run_id: str,
    status: str,
    results: list[dict[str, Any]],
) -> None:
    """Persist terminal execution state and each per-model result atomically."""
    if status not in {"COMPLETED", "PARTIAL"}:
        raise ValueError("unsupported Arena execution status")
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE arena_runs
                SET status = %s, results = %s, updated_at = NOW()
                WHERE id = %s AND organization_id = %s AND status = 'RUNNING'
                """,
                (status, Json(results), run_id, organization_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Arena run is missing, foreign, or no longer RUNNING")
            for result in results:
                cursor.execute(
                    """
                    INSERT INTO arena_results (
                        id, run_id, model_id, execution_status, evidence_verdict,
                        raw_response, trace_id, cost_estimate_rub, error, result
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        result["model"],
                        result["execution_status"],
                        result["evidence_verdict"],
                        result.get("raw_response"),
                        result["trace_id"],
                        str(result.get("cost_estimate_rub", "UNKNOWN")),
                        Json(result["error"]) if result.get("error") is not None else None,
                        Json(result),
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        release_connection(connection)
