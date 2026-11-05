"""Temporal snapshot integrity and translation tests."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from jamp.server.checks import engine, temporal


def _wheel_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("samplepkg/__init__.py", "def ok():\n    return True\n")
    return output.getvalue()


def _write_snapshot(root: Path, wheel: bytes, expected_sha: str) -> Path:
    record = {
        "sample_id": "sample-1",
        "package_name": "samplepkg",
        "pypi_version": "1.0",
        "wheel_filename": "samplepkg-1.0-py3-none-any.whl",
        "wheel_sha256": expected_sha,
        "wheel_relative_path": "wheelhouse/sample.whl",
        "resolution_status": "RESOLVED",
        "temporal_provenance": "PRE_GENERATION_REGISTRY_SNAPSHOT",
    }
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir(parents=True)
    (wheelhouse / "sample.whl").write_bytes(wheel)
    snapshot_path = root / "generation_snapshot.json"
    temporal.write_generation_snapshot(
        snapshot_path,
        generation_timestamp_utc="2026-11-05T00:00:00Z",
        provider_name="test",
        requested_model_id="test/model",
        provider_model_id="test/model",
        generation_environment={"installed_distributions": []},
        packages=[record],
    )
    return snapshot_path


def test_temporal_wheel_sha_mismatch_translates_to_integrity_violated(tmp_path: Path):
    snapshot_path = _write_snapshot(tmp_path, b"tampered-wheel", "0" * 64)
    with (
        patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}),
        patch.object(temporal, "_wheel_compatible_with_cpython311_linux_x86_64", return_value=True),
    ):
        result = engine.verify_code(
            "import samplepkg\nsamplepkg.ok()",
            "samplepkg",
            temporal_snapshot=snapshot_path,
            sample_id="sample-1",
        )
    assert result["status"] == "INTEGRITY_VIOLATED"
    assert result["reason"] == "temporal_wheel_sha256_mismatch"


def test_temporal_snapshot_manifest_sha_mismatch_is_integrity_violation(tmp_path: Path):
    snapshot_path = _write_snapshot(tmp_path, b"unused", "0" * 64)
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    payload["generation_timestamp_utc"] = "2026-11-06T00:00:00Z"
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    with patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}):
        result = engine.verify_code(
            "import samplepkg", "samplepkg", temporal_snapshot=snapshot_path, sample_id="sample-1"
        )
    assert result["status"] == "INTEGRITY_VIOLATED"
    assert result["reason"] == "temporal_snapshot_sha256_mismatch"


def test_valid_temporal_wheel_and_trusted_provenance_are_clean(tmp_path: Path):
    wheel = _wheel_bytes()
    digest = hashlib.sha256(wheel).hexdigest()
    snapshot_path = _write_snapshot(tmp_path, wheel, digest)
    with (
        patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}),
        patch.object(temporal, "_wheel_compatible_with_cpython311_linux_x86_64", return_value=True),
    ):
        result = engine.verify_code(
            "import samplepkg\nsamplepkg.ok()",
            "samplepkg",
            temporal_snapshot=snapshot_path,
            sample_id="sample-1",
        )
    assert result["status"] == "CLEAN"
    assert result["signature"]["status"] == "EXISTS"


def test_missing_temporal_record_fails_closed(tmp_path: Path):
    snapshot_path = _write_snapshot(tmp_path, b"unused", "0" * 64)
    with patch.object(engine, "check_provenance", return_value={"status": "TRUSTED"}):
        result = engine.verify_code(
            "import samplepkg", "samplepkg", temporal_snapshot=snapshot_path, sample_id="missing"
        )
    assert result["status"] == "INCONCLUSIVE"
