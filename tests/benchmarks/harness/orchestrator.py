"""Parent orchestrator for P24-A cold-replay stage telemetry."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from tests.benchmarks.fixtures.e2e_synthetic_discovery import OBS_B, create_tick_2_fixture
from tests.benchmarks.harness.snapshot_schema import dump_snapshot


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKER_MODULE = "tests.benchmarks.harness.benchmark_worker"


def run_p24_a_telemetry() -> dict[str, Any]:
    """Generate a physical snapshot and execute one fresh telemetry worker."""
    fixture = create_tick_2_fixture()

    with tempfile.TemporaryDirectory(prefix="jamp-p24-a-") as temporary_dir:
        snapshot_path = Path(temporary_dir) / "snapshot.json"
        dump_snapshot(
            fixture.graph,
            fixture.ledger,
            [fixture.hypothesis_h1, fixture.hypothesis_h2],
            snapshot_path,
        )

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                WORKER_MODULE,
                "--snapshot",
                str(snapshot_path),
                "--target-hash",
                OBS_B,
                "--hypothesis-index",
                "0",
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    output = completed.stdout.strip().splitlines()
    if not output:
        raise RuntimeError("P24-A worker produced no telemetry")
    return json.loads(output[-1])


def main() -> int:
    print(json.dumps(run_p24_a_telemetry(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
