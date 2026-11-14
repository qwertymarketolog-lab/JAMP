from __future__ import annotations

import json
import sys
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
        "provider": audit.MODEL_REGISTRY["model_001"]["provider"],
        "model_id": audit.MODEL_REGISTRY["model_001"]["model_id"],
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
        "usage": {},
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
        "repository_commit_sha": "d" * 40,
        "source_run_id": "123",
        "source_artifact_id": "456",
        "usage": usage,
    }
    (tmp_path / "model.metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = {
        "status": "COMPLETED",
        "experiment_id": metadata["experiment_id"],
        "repository_commit_sha": "d" * 40,
        "enabled_models": [model_key],
        "available_models": [model_key],
        "executed_models": [model_key],
        "completed_models": [model_key],
        "skipped_models": [],
        "failed_models": [],
        "still_running": [],
        "usage": {model_key: usage},
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



def test_execute_rejects_catalog_snapshot_digest_mismatch_before_api_key(tmp_path):
    snapshot = tmp_path / "catalog_snapshot.json"
    snapshot.write_bytes(b'{"data":[]}')
    with pytest.raises(ValueError, match="integrity mismatch"):
        audit.execute(
            ["model_001"],
            str(uuid.uuid4()),
            snapshot,
            "0" * 64,
            0,
            tmp_path,
        )


def test_execute_requires_matching_preflight_record_before_api_key(
    tmp_path, monkeypatch
):
    catalog = {
        "data": [
            {"id": item["model_id"]}
            for item in audit.MODEL_REGISTRY.values()
        ]
    }
    raw = json.dumps(catalog).encode("utf-8")
    snapshot = tmp_path / "catalog_snapshot.json"
    snapshot.write_bytes(raw)
    experiment_id = str(uuid.uuid4())
    preflight = {
        "experiment_id": str(uuid.uuid4()),
        "catalog_sha256": audit.sha256(raw),
        "selected_model_keys": ["model_001"],
        "available_models": ["model_001"],
        "skipped_models": [],
        "repository_commit_sha": audit.git_commit_sha(),
    }
    (tmp_path / "preflight.json").write_text(json.dumps(preflight), encoding="utf-8")
    monkeypatch.delenv("ANYMODEL_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Preflight record"):
        audit.execute(
            ["model_001"],
            experiment_id,
            snapshot,
            audit.sha256(raw),
            0,
            tmp_path,
        )



def test_manifest_rejects_usage_disagreement(tmp_path):
    manifest = _valid_manifest(tmp_path)
    manifest["usage"] = {"model_001": {"prompt_tokens": 1}}
    with pytest.raises(ValueError, match="usage mismatch"):
        audit.validate_manifest(manifest, tmp_path)


def test_compute_estimate_tokens_uses_full_composite_utf8_payload(tmp_path, monkeypatch):
    pack = tmp_path / "INPUT_PACK.md"
    pack.write_text("Пакет", encoding="utf-8")
    monkeypatch.setattr(audit, "AUDIT_PROMPT", "AUDIT")
    monkeypatch.setattr(audit, "INPUT_PACK_PATH", pack)

    expected = "AUDIT\\n\\n### INPUT PACK\\nПакет".encode("utf-8")
    estimate = audit.compute_estimate_tokens()

    assert estimate == {
        "composite_bytes": len(expected),
        "estimated_prompt_tokens_heuristic": (len(expected) + 1) // 2,
        "max_output_tokens_per_model": 4096,
        "note": (
            "Heuristic: ~1 token per 2 UTF-8 bytes of composite prompt. "
            "Not a forecast."
        ),
    }


def test_preflight_writes_revision6_model_and_estimate_contract(
    tmp_path, monkeypatch
):
    catalog = {
        "data": [
            {"id": audit.MODEL_REGISTRY["model_001"]["model_id"]},
            {"id": audit.MODEL_REGISTRY["model_002"]["model_id"]},
        ]
    }
    raw = json.dumps(catalog).encode("utf-8")
    monkeypatch.setenv("ANYMODEL_API_KEY", "test-key")
    monkeypatch.setattr(audit, "http_get_catalog", lambda _key: raw)
    monkeypatch.setattr(audit, "git_commit_sha", lambda: "a" * 40)
    monkeypatch.setattr(
        audit,
        "compute_estimate_tokens",
        lambda: {
            "composite_bytes": 7000,
            "estimated_prompt_tokens_heuristic": 3500,
            "max_output_tokens_per_model": 4096,
            "note": "test heuristic",
        },
    )
    experiment_id = str(uuid.uuid4())
    output_dir = tmp_path / experiment_id

    digest = audit.preflight(audit.select_models("all"), experiment_id, output_dir)
    record = json.loads((output_dir / "preflight.json").read_text(encoding="utf-8"))

    assert (output_dir / "catalog_snapshot.json").read_bytes() == raw
    assert digest == audit.sha256(raw) == record["catalog_sha256"]
    assert record["available_models"] == ["model_001", "model_002"]
    assert record["skipped_models"] == [
        {"key": "model_003", "reason": "MODEL_NOT_IN_CATALOG"}
    ]
    assert record["estimated"]["composite_bytes"] == 7000
    assert record["estimated"]["estimated_prompt_tokens_heuristic"] == 3500
    assert record["estimated"]["max_output_tokens_per_model"] == 4096


def test_preflight_cli_emits_dry_run_marker_only_after_evidence_is_written(
    tmp_path, monkeypatch, capsys
):
    catalog = {
        "data": [
            {"id": item["model_id"]}
            for item in audit.MODEL_REGISTRY.values()
        ]
    }
    raw = json.dumps(catalog).encode("utf-8")
    monkeypatch.setenv("ANYMODEL_API_KEY", "test-key")
    monkeypatch.setattr(audit, "http_get_catalog", lambda _key: raw)
    monkeypatch.setattr(audit, "git_commit_sha", lambda: "b" * 40)
    monkeypatch.setattr(audit, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(
        audit,
        "compute_estimate_tokens",
        lambda: {
            "composite_bytes": 7000,
            "estimated_prompt_tokens_heuristic": 3500,
            "max_output_tokens_per_model": 4096,
            "note": "test heuristic",
        },
    )
    monkeypatch.setattr(
        audit, "execute",
        lambda *args, **kwargs: pytest.fail("preflight must never execute paid requests"),
    )
    experiment_id = str(uuid.uuid4())
    monkeypatch.setattr(
        sys, "argv",
        ["jamp_audit_v1.py", "preflight", "--models", "all",
         "--experiment-id", experiment_id],
    )

    assert audit.main() == 0
    output = capsys.readouterr().out
    evidence_dir = tmp_path / experiment_id
    assert (evidence_dir / "preflight.json").is_file()
    assert (evidence_dir / "catalog_snapshot.json").is_file()
    assert "DRY-RUN: preflight OK" in output
    assert "estimated_prompt_tokens_heuristic: 3500" in output
    assert "available_models: 3" in output
    assert "skipped_models: 0" in output
