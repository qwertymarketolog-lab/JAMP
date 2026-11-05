"""PostgreSQL persistence for tenant-scoped verification verdicts."""
from __future__ import annotations
import hashlib, json, uuid
from datetime import UTC, datetime
from typing import Any
from psycopg2.extras import Json
from jamp.db.connection import get_connection, release_connection

class IdempotencyConflict(ValueError):
    """An idempotency key was reused for a different request."""

def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()

def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict): return value
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, dict): return decoded
    raise ValueError("stored JSON value is not an object")

def _read_evidence(cursor: Any, verdict_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        "SELECT sequence_no, evidence_type, payload, payload_hash, created_at "
        "FROM evidence_chain WHERE verdict_id = %s ORDER BY sequence_no", (verdict_id,))
    return [{"sequence_no": r[0], "evidence_type": r[1], "payload": _as_dict(r[2]),
             "payload_hash": r[3].strip(), "created_at": r[4].isoformat()}
            for r in cursor.fetchall()]

def persist_or_get_verdict(*, organization_id: str, idempotency_key: str,
                           request_hash: str, code_hash: str,
                           result: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Atomically persist verdict/evidence or return the original idempotent result."""
    allowed = {"CLEAN", "SUSPICIOUS", "HALLUCINATION_CAUGHT", "INCONCLUSIVE", "INTEGRITY_VIOLATED"}
    if result.get("status") not in allowed: raise ValueError("unsupported verification status")
    if len(request_hash) != 64 or len(code_hash) != 64: raise ValueError("invalid SHA-256 digest")
    lock = hashlib.sha256((organization_id + "\0" + idempotency_key).encode()).digest()
    lock_id = int.from_bytes(lock[:8], "big", signed=True)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            cur.execute("SELECT id, request_hash, result, created_at FROM verdicts "
                        "WHERE organization_id=%s AND idempotency_key=%s",
                        (organization_id, idempotency_key))
            old = cur.fetchone()
            if old:
                vid, old_hash, old_result, created = old
                old_payload = _as_dict(old_result)
                if old_hash.strip() != request_hash: raise IdempotencyConflict
                response = {"verdict_id": str(vid), "status": old_payload["status"],
                            "result": old_payload, "evidence": _read_evidence(cur, str(vid)),
                            "created_at": created.isoformat(), "code_hash": code_hash}
                conn.commit()
                return response, False
            vid, created = str(uuid.uuid4()), datetime.now(UTC)
            cur.execute("INSERT INTO verdicts "
                        "(id,organization_id,idempotency_key,request_hash,code_hash,status,sample_id,result,created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (vid, organization_id, idempotency_key, request_hash, code_hash,
                         result["status"], result.get("sample_id"), Json(result), created))
            evidence = [(k,v) for k,v in (("provenance",result.get("provenance")),
                        ("signature",result.get("signature"))) if isinstance(v,dict)]
            rows=[]
            for seq,(kind,payload) in enumerate(evidence):
                digest=_payload_hash(payload)
                cur.execute("INSERT INTO evidence_chain "
                            "(id,verdict_id,sequence_no,evidence_type,payload,payload_hash) "
                            "VALUES (%s,%s,%s,%s,%s,%s)",
                            (str(uuid.uuid4()),vid,seq,kind,Json(payload),digest))
                rows.append({"sequence_no":seq,"evidence_type":kind,"payload":payload,
                             "payload_hash":digest,"created_at":created.isoformat()})
        conn.commit()
        return {"verdict_id":vid,"status":result["status"],"result":result,
                "evidence":rows,"created_at":created.isoformat(),"code_hash":code_hash}, True
    except Exception:
        conn.rollback()
        raise
    finally:
        release_connection(conn)
