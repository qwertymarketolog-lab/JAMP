"""P27 incremental audit-log exporter with P36.1 contract evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from jamp.runtime.provenance import validate_audit_trace


class UploadResult:
    def __init__(self, success: bool, status_code: int | None = None):
        self.success = success
        self.status_code = status_code
        self.payload_sha256: str | None = None
        self.batch_id: str | None = None
        self.trace_ids: tuple[str, ...] = ()
        self.metadata: dict[str, str] = {}


class StorageAdapter(Protocol):
    def upload(
        self,
        object_key: str,
        payload_bytes: bytes,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult: ...


class S3StorageAdapter:
    """S3-compatible object storage using AWS Signature Version 4."""

    def __init__(self, endpoint_url: str, bucket_name: str):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket_name = bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=os.environ.get("JAMP_G4_MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.environ.get("JAMP_G4_MINIO_SECRET_KEY", "minioadminpassword"),
            region_name=os.environ.get("JAMP_G4_MINIO_REGION", "us-east-1"),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def upload(
        self,
        object_key: str,
        payload_bytes: bytes,
        metadata: dict[str, str] | None = None,
    ) -> UploadResult:
        try:
            response = self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=payload_bytes,
                ContentType="application/x-ndjson",
                Metadata=metadata or {},
            )
        except (BotoCoreError, ClientError):
            return UploadResult(False)
        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return UploadResult(status_code in (200, 201, 204), status_code)

    def download(self, object_key: str) -> bytes:
        """Download an object from the configured bucket."""
        response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
        return response["Body"].read()


class AuditLogExporter:
    """Incremental, at-least-once exporter for append-only JSONL."""

    def __init__(
        self,
        audit_file_path: str,
        state_file_path: str,
        storage_adapter: StorageAdapter,
    ):
        self.audit_file_path = Path(audit_file_path)
        self.state_file_path = Path(state_file_path)
        self.storage_adapter = storage_adapter
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_cursor(self) -> int:
        if not self.state_file_path.exists():
            return 0
        try:
            data = json.loads(self.state_file_path.read_text(encoding="utf-8"))
            offset = int(data["last_offset"])
            return max(0, offset)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return 0

    def _write_cursor(self, offset: int) -> None:
        tmp = self.state_file_path.with_suffix(self.state_file_path.suffix + ".tmp")
        tmp.write_text(json.dumps({"last_offset": offset}), encoding="utf-8")
        with tmp.open("rb") as f:
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self.state_file_path)
        try:
            directory_fd = os.open(self.state_file_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass

    @staticmethod
    def _batch_identity(payload: bytes) -> str:
        return "batch_" + hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _trace_ids(payload: bytes) -> tuple[str, ...]:
        trace_ids: list[str] = []
        for line in payload.splitlines():
            record = json.loads(line)
            validate_audit_trace(record)
            trace_id = record.get("trace_id")
            if isinstance(trace_id, str) and trace_id and trace_id not in trace_ids:
                trace_ids.append(trace_id)
        return tuple(trace_ids)

    def export_pending(self) -> dict[str, Any]:
        if not self.audit_file_path.exists():
            return {"status": "NO_FILE", "exported_records": 0, "bytes_sent": 0}

        cursor = self._read_cursor()
        file_size = self.audit_file_path.stat().st_size
        if cursor > file_size:
            cursor = 0

        with self.audit_file_path.open("rb") as source:
            source.seek(cursor)
            start = cursor
            payload = bytearray()
            records = 0
            while True:
                line = source.readline()
                if not line:
                    break
                if not line.endswith(b"\n"):
                    break
                if line.strip():
                    payload.extend(line)
                    records += 1
                cursor = source.tell()

        if not payload:
            return {
                "status": "PARTIAL_RECORD_PENDING" if start < file_size else "UP_TO_DATE",
                "exported_records": 0,
                "bytes_sent": 0,
                "start_offset": start,
                "end_offset": start,
            }

        payload_bytes = bytes(payload)
        end = cursor
        batch_id = self._batch_identity(payload_bytes)
        trace_ids = self._trace_ids(payload_bytes)
        metadata = {
            "batch-id": batch_id,
            "trace-ids": ",".join(trace_ids),
        }
        payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        object_key = f"audit/{start}-{end}.jsonl"

        result = self.storage_adapter.upload(object_key, payload_bytes, metadata)
        result.payload_sha256 = payload_sha256
        result.batch_id = batch_id
        result.trace_ids = trace_ids
        result.metadata = dict(metadata)

        if not result.success:
            return {
                "status": "UPLOAD_FAILED",
                "exported_records": 0,
                "bytes_sent": 0,
                "start_offset": start,
                "end_offset": start,
                "object_key": object_key,
                "payload_sha256": payload_sha256,
                "batch_id": batch_id,
                "trace_ids": list(trace_ids),
                "storage_metadata": metadata,
            }

        self._write_cursor(end)
        return {
            "status": "SUCCESS",
            "exported_records": records,
            "bytes_sent": len(payload_bytes),
            "start_offset": start,
            "end_offset": end,
            "object_key": object_key,
            "payload_sha256": payload_sha256,
            "batch_id": batch_id,
            "trace_ids": list(trace_ids),
            "storage_metadata": metadata,
        }
