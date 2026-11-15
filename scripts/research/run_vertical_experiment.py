from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "docs/experiments/jamp_audit_v1/vertical_experiment_v1.json"
TEST_TARGET = "tests/research/test_vertical_experiment.py"
ARTIFACT_DIR = ROOT / "artifacts/research/jamp_audit_v1/vertical_experiment"
ARTIFACT_PATH = ARTIFACT_DIR / "vertical_experiment_result.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    started_at = _utc_now()
    dataset_bytes = DATASET.read_bytes()
    dataset = json.loads(dataset_bytes)
    if dataset.get("mode") != "offline_mock_only" or len(dataset.get("cases", [])) != 10:
        raise SystemExit("REFUSE: dataset contract must contain exactly ten offline mock cases")

    command = [sys.executable, "-m", "pytest", "-q", TEST_TARGET]
    env = os.environ.copy()
    source_root = str(ROOT / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, existing_pythonpath) if value
    )
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    finished_at = _utc_now()
    result = {
        "schema_version": "1.0",
        "experiment_id": dataset["experiment_id"],
        "status": "SUCCESS" if completed.returncode == 0 else "FAILURE",
        "started_at": started_at,
        "finished_at": finished_at,
        "dataset_path": str(DATASET.relative_to(ROOT)),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "test_command": command,
        "test_exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "case_count": len(dataset["cases"]),
        "network_mode": "offline_mock_only",
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["status"],
        "artifact": str(ARTIFACT_PATH.relative_to(ROOT)),
        "dataset_sha256": result["dataset_sha256"],
        "test_exit_code": completed.returncode,
    }, ensure_ascii=False))
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
