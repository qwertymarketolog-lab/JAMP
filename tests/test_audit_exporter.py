import json
from unittest.mock import MagicMock

from src.jamp.audit.exporter import AuditLogExporter, S3StorageAdapter, UploadResult


def make_exporter(tmp_path, adapter):
    return AuditLogExporter(
        str(tmp_path / "provenance_traces.jsonl"), str(tmp_path / "state.json"), adapter
    )


def test_incremental_cursor_and_idempotent_batch(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_text(json.dumps({"trace_id": "tr_1"}) + "\n", encoding="utf-8")
    adapter = MagicMock(spec=S3StorageAdapter)
    adapter.upload.return_value = UploadResult(True, 200)
    exporter = make_exporter(tmp_path, adapter)
    first = exporter.export_pending()
    assert first["status"] == "SUCCESS"
    assert first["exported_records"] == 1
    assert exporter.export_pending()["status"] == "UP_TO_DATE"
    assert adapter.upload.call_count == 1
    audit.write_text(
        audit.read_text(encoding="utf-8") + json.dumps({"trace_id": "tr_2"}) + "\n",
        encoding="utf-8",
    )
    second = exporter.export_pending()
    assert second["status"] == "SUCCESS"
    assert second["exported_records"] == 1
    assert adapter.upload.call_count == 2


def test_partial_line_waits_for_newline(tmp_path):
    audit = tmp_path / "provenance_traces.jsonl"
    audit.write_text(json.dumps({"trace_id": "tr_1"}) + "\npartial", encoding="utf-8")
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
    audit.write_text(json.dumps({"trace_id": "tr_1"}) + "\n", encoding="utf-8")
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
