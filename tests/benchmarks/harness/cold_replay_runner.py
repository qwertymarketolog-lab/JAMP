"""Orchestrator for managing isolated cold replay process spawning and state assertion."""

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Dict, List

from jamp.research.lineage_graph import LineageGraph
from tests.benchmarks.fixtures.e2e_synthetic_discovery import (
    EvidenceLedger,
    SyntheticHypothesis,
)
from tests.benchmarks.harness.snapshot_schema import dump_snapshot


def run_cold_replay(
    graph: LineageGraph,
    ledger: EvidenceLedger,
    hypotheses: List[SyntheticHypothesis],
    tmp_path: Path,
) -> Dict[str, float]:
    """Executes scoring via disk persistence and fresh sub-process isolation."""
    snapshot_path = tmp_path / "snapshot.json"
    output_path = tmp_path / "output.json"

    # 1. Dump in-memory snapshot to disk
    dump_snapshot(graph, ledger, hypotheses, snapshot_path)

    # 2. Locate worker script and determine repository paths
    harness_dir = Path(__file__).resolve().parent
    worker_script = harness_dir / "cold_replay_worker.py"
    repo_root = harness_dir.parents[2]
    src_dir = repo_root / "src"

    # 3. Explicitly construct environment with repository root and src in PYTHONPATH
    env = os.environ.copy()
    python_path_entries = [str(repo_root), str(src_dir)]
    if "PYTHONPATH" in env:
        python_path_entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries)

    # 4. Spawn isolated sub-process with clean interpreter context
    cmd = [
        sys.executable,
        str(worker_script),
        "--snapshot",
        str(snapshot_path),
        "--output",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0 and not output_path.exists():
        raise RuntimeError(
            f"Subprocess cold replay worker crashed unexpectedly:\n{result.stderr}"
        )

    # 5. Parse sub-process output
    with open(output_path, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    if output_data.get("status") == "ERROR":
        error_type = output_data.get("error_type")
        error_msg = output_data.get("error_message", "")
        if error_type == "ValueError":
            raise ValueError(error_msg)
        raise RuntimeError(f"Subprocess raised {error_type}: {error_msg}")

    return output_data["scores"]
