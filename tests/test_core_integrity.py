from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_core_integrity.py"
MANIFEST = ROOT / "integrity" / "core-manifest-v0.json"
CORE = ROOT / "src" / "jamp" / "run.py"


def run_verifier(root: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), "--root", str(root), "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_frozen_core_matches_canonical_identity() -> None:
    result = run_verifier(ROOT, MANIFEST)

    assert result.returncode == 0, result.stderr
    assert "PASS CIC-v0" in result.stdout


def test_core_mutation_fails_closed(tmp_path: Path) -> None:
    temp_root = tmp_path / "repo"
    shutil.copytree(ROOT, temp_root, ignore=shutil.ignore_patterns(".git"))
    target = temp_root / "src" / "jamp" / "run.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# unauthorized mutation\n", encoding="utf-8")

    result = run_verifier(temp_root, temp_root / "integrity" / "core-manifest-v0.json")

    assert result.returncode != 0
    assert "CORE_INTEGRITY_VIOLATION" in result.stderr
    assert "expected" in result.stderr
    assert "observed" in result.stderr


def test_manifest_mutation_fails_closed(tmp_path: Path) -> None:
    temp_root = tmp_path / "repo"
    shutil.copytree(ROOT, temp_root, ignore=shutil.ignore_patterns(".git"))
    manifest = temp_root / "integrity" / "core-manifest-v0.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["canonical_files"][0]["git_blob_sha1"] = "0" * 40
    manifest.write_text(json.dumps(data), encoding="utf-8")

    result = run_verifier(temp_root, manifest)

    assert result.returncode != 0
    assert "CORE_INTEGRITY_VIOLATION" in result.stderr
