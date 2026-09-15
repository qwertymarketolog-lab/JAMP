from __future__ import annotations

import json
import subprocess
from pathlib import Path

from exp03_adapter import Exp03Adapter
from exp03_export import run_exp03
from exp03_graph import G

EXPECTED_RUN_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
EXPECTED_PATH = ["S", "A", "X", "B", "G"]


def test_exp03_search_transfer():
    repo_root = Path(__file__).resolve().parents[2]
    run_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:src/jamp/run.py"],
        cwd=repo_root,
        text=True,
    ).strip()
    assert run_blob == EXPECTED_RUN_BLOB

    result, artifact = run_exp03()

    assert result.steps == 5
    assert result.iterations == 5
    assert result.stop_reason.kind == "terminal"

    final_state = artifact["final_state"]
    assert G.name in final_state["visited"]
    assert final_state["visited"] == EXPECTED_PATH

    provenance = artifact["provenance"]
    assert len(provenance) == result.steps
    assert [entry["selected"] for entry in provenance] == EXPECTED_PATH
    assert provenance[2]["after"]["frontier"] == ["B"]
    assert provenance[3]["after"]["frontier"] == ["G"]

    restored = json.loads(json.dumps(artifact, ensure_ascii=False))
    assert restored == artifact


def test_exp03_provenance_is_linear_search_state_chain():
    adapter = Exp03Adapter()
    result = __import__("jamp.run", fromlist=["run"]).run(adapter)

    assert result.steps == 5
    assert len(adapter.history) == result.steps
    for previous, _selected, current in adapter.history:
        assert previous.current != current.current or previous != current
