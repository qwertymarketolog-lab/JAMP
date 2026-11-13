from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from scripts.research import jamp_audit_v1 as audit


@pytest.mark.parametrize(
    ("status", "content", "finish", "expected"),
    [
        (200, "answer", "stop", audit.FinalStatus.COMPLETED),
        (200, "", "stop", audit.FinalStatus.EMPTY),
        (200, None, "stop", audit.FinalStatus.EMPTY),
        (200, "partial", "length", audit.FinalStatus.TRUNCATED),
        (200, "", "length", audit.FinalStatus.EMPTY),
        (200, None, "length", audit.FinalStatus.EMPTY),
        (200, "   ", "length", audit.FinalStatus.TRUNCATED),
        (200, "blocked", "content_filter", audit.FinalStatus.CONTENT_FILTERED),
        (503, "ignored", "stop", audit.FinalStatus.API_ERROR),
    ],
)
def test_classify_response_table(status, content, finish, expected):
    body = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
    assert audit.classify_response(status, body) == expected


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": 3}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": ["x"]}, "finish_reason": "stop"}]},
        {"choices": [{"message": {"content": "x"}, "finish_reason": None}]},
        {"choices": [{"message": {"content": "x"}, "finish_reason": "tool_calls"}]},
        {"choices": [{"message": {"content": "   "}, "finish_reason": "stop"}]},
    ],
)
def test_classify_malformed_response_is_invalid(body):
    assert audit.classify_response(200, body) == audit.FinalStatus.INVALID_RESPONSE


def test_registry_and_model_selection_are_bounded():
    audit.validate_registry()
    assert audit.select_models("all") == ["model_001", "model_002", "model_003"]
    assert audit.select_models("model_001,model_003") == ["model_001", "model_003"]


@pytest.mark.parametrize("value", ["model_001,model_001", "bad-key", "unknown", ""])
def test_rejects_invalid_model_selection(value):
    with pytest.raises(ValueError):
        audit.select_models(value)


def test_registry_rejects_boolean_integer_parameter():
    registry = {
        "model_001": {
            "provider": "anymodel", "model_id": "vendor/model",
            "enabled": True,
            "request_params": {"max_tokens": True, "temperature": 0},
        }
    }
    with pytest.raises(ValueError):
        audit.validate_registry(registry)


def test_registry_rejects_non_anymodel_provider():
    registry = {
        "model_001": {
            "provider": "other", "model_id": "vendor/model",
            "enabled": True, "request_params": {"max_tokens": 10, "temperature": 0},
        }
    }
    with pytest.raises(NotImplementedError):
        audit.validate_registry(registry)


def test_uuid_must_be_canonical_uuid4():
    assert audit.canonical_uuid(str(uuid.uuid4()))
    assert not audit.canonical_uuid("not-a-uuid")
    assert not audit.canonical_uuid("00000000-0000-0000-0000-000000000000")


def test_snapshot_round_trip_uses_exact_input_bytes(tmp_path, monkeypatch):
    pack = tmp_path / "INPUT_PACK.md"
    pack.write_bytes(b"line one\r\nline two\n")
    monkeypatch.setattr(audit, "INPUT_PACK_PATH", pack)
    snapshots = tmp_path / "snapshots"
    audit.emit_snapshots(snapshots)
    audit.verify_snapshots(snapshots)
    pack.write_bytes(b"line one\nline two\n")
    with pytest.raises(ValueError, match="input_pack"):
        audit.verify_snapshots(snapshots)


def _valid_manifest(tmp_path: Path) -> dict:
    experiment_id = str(uuid.uuid4())
    hashes = {
        "audit_spec_sha256": audit.sha256(audit.AUDIT_PROMPT.encode("utf-8")),
        "input_pack_sha256": audit.sha256(audit.INPUT_PACK_PATH.read_bytes()),
        "prompt_sha256": audit.sha256(audit.composite_prompt().encode("utf-8")),
    }
    response = b"audited response\n"
    (tmp_path / "model_001.md").write_bytes(response)
    metadata = {
        "model_key": "model_001",
        "experiment_id": experiment_id,
        "repository_commit_sha": audit.git_commit_sha(),
        **hashes,
        "status": "COMPLETED",
        "response_sha256": audit.sha256(response),
    }
    (tmp_path / "model_001.metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return {
        "experiment_id": experiment_id,
        "repository_commit_sha": audit.git_commit_sha(),
        **hashes,
        "enabled_models": ["model_001"],
        "available_models": ["model_001"],
        "skipped_models": [],
        "executed_models": ["model_001"],
        "completed_models": ["model_001"],
        "failed_models": [],
        "still_running": [],
        "metadata_files": {"model_001": "model_001.metadata.json"},
        "response_files": {"model_001": "model_001.md"},
        "status": "COMPLETED",
    }


def test_terminal_manifest_accepts_consistent_completed_batch(tmp_path):
    manifest = _valid_manifest(tmp_path)
    audit.validate_manifest(manifest, tmp_path)


def test_manifest_rejects_duplicate_model_keys(tmp_path):
    manifest = _valid_manifest(tmp_path)
    manifest["executed_models"] = ["model_001", "model_001"]
    with pytest.raises(ValueError, match="duplicates"):
        audit.validate_manifest(manifest, tmp_path)


def test_manifest_rejects_missing_metadata(tmp_path):
    manifest = _valid_manifest(tmp_path)
    manifest["metadata_files"] = {}
    with pytest.raises(ValueError, match="Metadata files"):
        audit.validate_manifest(manifest, tmp_path)


def test_manifest_rejects_response_checksum_mismatch(tmp_path):
    manifest = _valid_manifest(tmp_path)
    (tmp_path / "model_001.md").write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="checksum"):
        audit.validate_manifest(manifest, tmp_path)


def test_manifest_rejects_failed_status_marked_completed(tmp_path):
    manifest = _valid_manifest(tmp_path)
    manifest["completed_models"] = []
    manifest["failed_models"] = [
        {"key": "model_001", "reason": "provider error", "status": "COMPLETED"}
    ]
    with pytest.raises(ValueError, match="cannot be COMPLETED"):
        audit.validate_manifest(manifest, tmp_path)


def test_manifest_requires_structured_skip_reason(tmp_path):
    manifest = _valid_manifest(tmp_path)
    manifest["enabled_models"] = ["model_001", "model_002"]
    manifest["available_models"] = ["model_001"]
    manifest["skipped_models"] = ["model_002"]
    with pytest.raises(ValueError, match="objects"):
        audit.validate_manifest(manifest, tmp_path)


def test_is_first_run_without_evidence_is_true(tmp_path, monkeypatch):
    path = tmp_path / "COST_BASELINE.md"
    path.write_text("# No evidence yet\n", encoding="utf-8")
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit.is_first_run(path)


def test_is_first_run_rejects_incomplete_manifest_metadata_chain(tmp_path, monkeypatch):
    path = tmp_path / "COST_BASELINE.md"
    path.write_text(
        "### model: vendor/model\n"
        "usage.prompt_tokens: 12\n"
        "usage.completion_tokens: 4\n"
        "source_run_id: 123\n"
        "source_artifact_id: 456\n"
        "manifest_file: missing.json\n"
        "metadata_file: missing-metadata.json\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit.is_first_run(path)


def test_is_first_run_rejects_boolean_like_usage(tmp_path, monkeypatch):
    path = tmp_path / "COST_BASELINE.md"
    path.write_text(
        "### model: vendor/model\n"
        "usage.prompt_tokens: True\n"
        "usage.completion_tokens: 4\n"
        "source_run_id: 123\nsource_artifact_id: 456\n"
        "manifest_file: manifest.json\nmetadata_file: metadata.json\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert audit.is_first_run(path)



def test_is_first_run_accepts_one_complete_evidence_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    model_key = "model_001"
    model_id = "vendor/model"
    usage = {"prompt_tokens": 12, "completion_tokens": 4}
    metadata = {
        "model_key": model_key,
        "model_id": model_id,
        "experiment_id": str(uuid.uuid4()),
        "status": "COMPLETED",
        "source_run_id": "123",
        "source_artifact_id": "456",
        "usage": usage,
    }
    (tmp_path / "model.metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = {
        "status": "COMPLETED",
        "experiment_id": metadata["experiment_id"],
        "completed_models": [model_key],
        "executed_models": [model_key],
        "metadata_files": {model_key: "model.metadata.json"},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    baseline = tmp_path / "COST_BASELINE.md"
    baseline.write_text(
        f"### model: {model_id}\n"
        "usage.prompt_tokens: 12\n"
        "usage.completion_tokens: 4\n"
        "source_run_id: 123\n"
        "source_artifact_id: 456\n"
        "manifest_file: manifest.json\n"
        "metadata_file: model.metadata.json\n",
        encoding="utf-8",
    )
    assert audit.is_first_run(baseline) is False
