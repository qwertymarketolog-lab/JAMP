"""CLI integration tests for the P17.6 empirical report artifact."""
from __future__ import annotations

import json
import subprocess
import sys


def test_closed_loop_export_verify_and_render(tmp_path) -> None:
    report_path = tmp_path / "experiment_report.json"

    export = subprocess.run(
        [
            sys.executable,
            "-m",
            "jamp.p17.closed_loop",
            "--export-report",
            str(report_path),
            "--generations",
            "4",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if export.returncode:
        print("P17.6 CLI stdout:\n" + export.stdout)
        print("P17.6 CLI stderr:\n" + export.stderr)
    assert export.returncode == 0, "P17.6 closed-loop CLI failed; see captured stdout/stderr above"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["generations"]) == 4
    assert report["report_digest"]
    assert "GEN | POLICY" in export.stdout

    verify = subprocess.run(
        [sys.executable, "-m", "jamp.p17.experiment_report", "--verify", str(report_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert verify.stdout.startswith("VALID: ")
    assert report["report_digest"] in verify.stdout

    render = subprocess.run(
        [sys.executable, "-m", "jamp.p17.experiment_report", "--render", str(report_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert render.stdout == export.stdout.split("Artifact: ", 1)[0]
    assert "ΔCE:" in render.stdout
    assert "Report digest:" in render.stdout
