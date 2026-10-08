import hashlib
import json
from unittest.mock import MagicMock

import pytest

from src.jamp.audit.exporter import AuditLogExporter, S3StorageAdapter, UploadResult
from src.jamp.runtime.provenance import AUDIT_TRACE_SCHEMA_VERSION, ProvenanceTracker, validate_audit_trace


def make_exporter(tmp_path, adapter):
    return AuditLogExporter(
        str(tmp_path / "provenance_traces.jsonl"), str(tmp_path / "state.json"), adapter
    )


def test_incremental_cursor_and_idempotent_batch(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_text(json.dumps({"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"}) + "\n", encoding="utf-8")
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)
    exporter = make_exporter(tmp_path, adapter)
    first = exporter.export_pending()
    assert first["status"] == "SUCCESS"
    assert first["exported_records"] == 1
    assert exporter.export_pending()["status"] == "UP_TO_DATE"
    assert adapter.upload.call_count == 1
    audit.write_text(
        audit.read_text(encoding="utf-8") + json.dumps({"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_2"}) + "\n",
        encoding="utf-8",
    )
    second = exporter.export_pending()
    assert second["status"] == "SUCCESS"
    assert second["exported_records"] == 1
    assert adapter.upload.call_count == 2


def test_partial_line_waits_for_newline(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_text(
        json.dumps({"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"}) + "\npartial",
        encoding="utf-8",
    )
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)
    exporter = make_exporter(tmp_path, adapter)
    result = exporter.export_pending()
    assert result["status"] == "SUCCESS"
    assert result["exported_records"] == 1
    assert exporter.export_pending()["status"] == "PARTIAL_RECORD_PENDING"
    assert adapter.upload.call_count == 1


def test_retry_keeps_cursor_on_upload_failure(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_text(
        json.dumps({"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"}) + "\n",
        encoding="utf-8",
    )
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.side_effect = [UploadResult(False, 503), UploadResult(True, 200)]
    exporter = make_exporter(tmp_path, adapter)
    failed = exporter.export_pending()
    assert failed["status"] == "UPLOAD_FAILED"
    assert not (tmp_path / "state.json").exists()
    retried = exporter.export_pending()
    assert retried["status"] == "SUCCESS"
    assert retried["exported_records"] == 1
    assert adapter.upload.call_count == 2


def test_missing_file(tmp_path):
    adapter = MagicMock(spec=S3StorageAdapter)
    exporter = make_exporter(tmp_path, adapter)
    assert exporter.export_pending()["status"] == "NO_FILE"


def test_trace_schema_version_required():
    trace = ProvenanceTracker().create_trace("tool_execution_agent", (), "REFUSE", "", 0)
    assert "schema_version" in trace


def test_trace_schema_version_value():
    trace = ProvenanceTracker().create_trace("tool_execution_agent", (), "REFUSE", "", 0)
    assert trace["schema_version"] == "jamp-audit-trace-v0.1"


def test_trace_schema_version_missing_is_contract_violation():
    trace = ProvenanceTracker().create_trace("tool_execution_agent", (), "REFUSE", "", 0)
    del trace["schema_version"]
    with pytest.raises(ValueError, match="schema_version contract violation"):
        validate_audit_trace(trace)


def test_payload_sha256_matches_payload(tmp_path):
    trace = {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"}
    payload = json.dumps(trace, sort_keys=True).encode() + b"\n"
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_bytes(payload)
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)

    result = make_exporter(tmp_path, adapter).export_pending()

    assert result["payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert adapter.upload.call_args.args[1] == payload


def test_payload_sha256_changes_when_payload_changes(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)
    exporter = make_exporter(tmp_path, adapter)

    payload_a = json.dumps(
        {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_a"}, sort_keys=True
    ).encode() + b"\n"
    audit.write_bytes(payload_a)
    first = exporter.export_pending()

    payload_b = json.dumps(
        {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_b"}, sort_keys=True
    ).encode() + b"\n"
    audit.write_bytes(payload_a + payload_b)
    second = exporter.export_pending()

    assert first["payload_sha256"] != second["payload_sha256"]


def test_export_identity_present(tmp_path):
    trace = {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"}
    payload = json.dumps(trace, sort_keys=True).encode() + b"\n"
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_bytes(payload)
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)

    result = make_exporter(tmp_path, adapter).export_pending()

    assert result["batch_id"] == "batch_" + hashlib.sha256(payload).hexdigest()
    assert result["batch_id"] != result["object_key"]


def test_trace_id_preserved_in_export_metadata(tmp_path):
    records = [
        {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"},
        {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_2"},
    ]
    payload = b"".join(json.dumps(record, sort_keys=True).encode() + b"\n" for record in records)
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_bytes(payload)
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)

    result = make_exporter(tmp_path, adapter).export_pending()

    assert result["trace_ids"] == ["tr_1", "tr_2"]
    assert result["storage_metadata"]["batch-id"] == result["batch_id"]
    assert result["storage_metadata"]["trace-ids"] == "tr_1,tr_2"
    assert adapter.upload.call_args.args[2] == result["storage_metadata"]


def test_batch_identity_independent_of_cursor_offsets(tmp_path):
    trace = {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_same"}
    payload = json.dumps(trace, sort_keys=True).encode() + b"\n"
    audit = tmp_path / "provenance_traces.jsonl"
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)

    prefix = json.dumps(
        {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "prefix"}, sort_keys=True
    ).encode() + b"\n"
    audit.write_bytes(prefix + payload)
    first = make_exporter(tmp_path, adapter).export_pending()

    audit.write_bytes(b"\n" + prefix + payload)
    (tmp_path / "state.json").unlink()
    second = make_exporter(tmp_path, adapter).export_pending()

    assert first["batch_id"] == second["batch_id"]


def test_existing_upload_failure_preserves_cursor(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    payload = json.dumps(
        {"schema_version": AUDIT_TRACE_SCHEMA_VERSION, "trace_id": "tr_1"}, sort_keys=True
    ).encode() + b"\n"
    audit.write_bytes(payload)
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(False, 503)

    result = make_exporter(tmp_path, adapter).export_pending()

    assert result["status"] == "UPLOAD_FAILED"
    assert result["start_offset"] == 0
    assert result["end_offset"] == 0
    assert result["payload_sha256"] == hashlib.sha256(payload).hexdigest()


def test_s3_object_metadata_contains_identity(monkeypatch):
    class Response:
        status_code = 200

    calls = []

    def fake_put(url, content, headers, timeout):
        calls.append((url, content, headers, timeout))
        return Response()

    monkeypatch.setattr("src.jamp.audit.exporter.httpx.put", fake_put)
    adapter = S3StorageAdapter("https://example.invalid", "bucket")
    result = adapter.upload(
        "audit/object.jsonl",
        b"payload",
        {"batch-id": "batch_test", "trace-ids": "tr_1"},
    )

    assert result.success is True
    assert calls[0][2]["x-amz-meta-batch-id"] == "batch_test"
    assert calls[0][2]["x-amz-meta-trace-ids"] == "tr_1"
