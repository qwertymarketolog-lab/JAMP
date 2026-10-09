"""Minimal G4 real S3-compatible runtime evidence test.

The test uses a real MinIO service supplied by the CI environment.
No mock replaces the storage HTTP boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx2 as httpx
import pytest

from src.jamp.audit.exporter import AuditLogExporter, S3StorageAdapter
from src.jamp.runtime.provenance import AUDIT_TRACE_SCHEMA_VERSION

MINIO_ENDPOINT = os.environ.get("JAMP_G4_MINIO_ENDPOINT")
MINIO_BUCKET = os.environ.get("JAMP_G4_MINIO_BUCKET", "jamp-g4")
MINIO_ACCESS_KEY = os.environ.get("JAMP_G4_MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("JAMP_G4_MINIO_SECRET_KEY", "minioadmin")
EVIDENCE_PATH = Path(os.environ.get("JAMP_G4_EVIDENCE_PATH", "artifacts/g4-runtime-evidence.json"))


def _require_runtime() -> None:
    if not MINIO_ENDPOINT:
        pytest.skip("JAMP_G4_MINIO_ENDPOINT is not configured")


def _wait_for_minio() -> None:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            response = httpx.get(
                f"{MINIO_ENDPOINT.rstrip('/')}/minio/health/live",
                timeout=2.0,
            )
            if response.status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(1)
    raise RuntimeError(f"MinIO health check failed: {last_error}")


def _put_object(endpoint: str, bucket: str, key: str, payload: bytes) -> None:
    response = httpx.put(
        f"{endpoint.rstrip('/')}/{bucket}/{key}",
        content=payload,
        timeout=10.0,
        auth=(MINIO_ACCESS_KEY, MINIO_SECRET_KEY),
    )
    response.raise_for_status()


def _get_object(endpoint: str, bucket: str, key: str) -> bytes:
    response = httpx.get(
        f"{endpoint.rstrip('/')}/{bucket}/{key}",
        timeout=10.0,
        auth=(MINIO_ACCESS_KEY, MINIO_SECRET_KEY),
    )
    response.raise_for_status()
    return response.content


def test_g4_minio_runtime_evidence(tmp_path: Path) -> None:
    _require_runtime()
    _wait_for_minio()

    # The MinIO service used by CI must already expose the configured bucket.
    # The test deliberately avoids adding a second storage implementation.
    probe_key = "g4/probe.txt"
    _put_object(MINIO_ENDPOINT, MINIO_BUCKET, probe_key, b"g4-probe")
    assert _get_object(MINIO_ENDPOINT, MINIO_BUCKET, probe_key) == b"g4-probe"

    audit_path = tmp_path / "provenance_traces.jsonl"
    state_path = tmp_path / "state.json"
    trace = {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "g4-trace-1"}
    payload = json.dumps(trace, sort_keys=True).encode() + b"\n"
    audit_path.write_bytes(payload)

    adapter = S3StorageAdapter(MINIO_ENDPOINT, MINIO_BUCKET)
    exporter = AuditLogExporter(str(audit_path), str(state_path), adapter)
    result = exporter.export_pending()

    assert result["status"] == "SUCCESS"
    assert result["payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["batch_id"] == "batch_" + hashlib.sha256(payload).hexdigest()
    assert state_path.exists()
    assert json.loads(state_path.read_text(encoding="utf-8"))["last_offset"] == len(payload)

    object_key = result["object_key"]
    downloaded = _get_object(MINIO_ENDPOINT, MINIO_BUCKET, object_key)
    downloaded_sha256 = hashlib.sha256(downloaded).hexdigest()
    assert downloaded == payload
    assert downloaded_sha256 == result["payload_sha256"]

    evidence = {
        "contract_version": "jamp-g4-runtime-v0.1",
        "commit_sha": os.environ.get("GITHUB_SHA", "unknown"),
        "frozen_core_blob": "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a",
        "storage_type": "minio",
        "bucket": MINIO_BUCKET,
        "object_key": object_key,
        "payload_sha256": result["payload_sha256"],
        "downloaded_sha256": downloaded_sha256,
        "sha256_match": downloaded_sha256 == result["payload_sha256"],
        "batch_id": result["batch_id"],
        "trace_ids": result["trace_ids"],
        "storage_metadata": result["storage_metadata"],
        "cursor_before": 0,
        "cursor_after": len(payload),
        "status": result["status"],
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
