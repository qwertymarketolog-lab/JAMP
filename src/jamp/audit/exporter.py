"""P27 incremental audit-log exporter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

import httpx2 as httpx


class UploadResult:
    def __init__(self, success: bool, status_code: int | None = None):
        self.success = success
        self.status_code = status_code


class StorageAdapter(Protocol):
    def upload(self, object_key: str, payload_bytes: bytes) -> UploadResult: ...


class S3StorageAdapter:
    """Minimal S3-compatible HTTP object-storage adapter."""

    def __init__(self, endpoint_url: str, bucket_name: str):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.bucket_name = bucket_name

    def upload(self, object_key: str, payload_bytes: bytes) -> UploadResult:
        url = f"{self.endpoint_url}/{self.bucket_name}/{object_key}"
        try:
            response = httpx.put(
                url,
                content=payload_bytes,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=10.0,
            )
        except httpx.HTTPError:
            return UploadResult(False)
        return UploadResult(
            response.status_code in (200, 201, 204), response.status_code
        )


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

        end = cursor
        object_key = f"audit/{start}-{end}.jsonl"
        result = self.storage_adapter.upload(object_key, bytes(payload))
        if not result.success:
            return {
                "status": "UPLOAD_FAILED",
                "exported_records": 0,
                "bytes_sent": 0,
                "start_offset": start,
                "end_offset": start,
                "object_key": object_key,
            }

        self._write_cursor(end)
        return {
            "status": "SUCCESS",
            "exported_records": records,
            "bytes_sent": len(payload),
            "start_offset": start,
            "end_offset": end,
            "object_key": object_key,
        }
