from __future__ import annotations

import json

from jamp.run import run
from scripts.artifact_v0 import serialize_run_result
from tests.research.puzzle8_run_adapter import GOAL, Puzzle8Adapter
from tests.research.track_a_run_adapter import TrackAAdapter


def _assert_artifact(artifact: dict, *, adapter: str) -> None:
    restored = json.loads(json.dumps(artifact, ensure_ascii=False))
    assert restored == artifact
    assert artifact["artifact_version"] == "v0"
    assert artifact["adapter"] == adapter
    assert set(artifact["run_result"]) == {"steps", "iterations", "stop_reason"}
    assert set(artifact["run_result"]["stop_reason"]) == {"kind", "detail"}
    assert "final_state" in artifact
    assert "provenance" in artifact
    assert artifact["provenance"]


def test_q3b3_production_integration_uses_real_adapters_and_run():
    track_adapter = TrackAAdapter(root=2, seed=42, N=500)
    track_result = run(track_adapter)
    track_artifact = serialize_run_result(
        track_result,
        adapter="track_a",
        final_state=[str(e) for e in track_result.state.objects],
        provenance=track_result.state.history,
    )

    puzzle_adapter = Puzzle8Adapter()
    puzzle_result = run(puzzle_adapter)
    puzzle_artifact = serialize_run_result(
        puzzle_result,
        adapter="8puzzle",
        final_state=list(puzzle_result.state),
        provenance=[
            [list(state), action, list(next_state)]
            for state, action, next_state in puzzle_adapter.history
        ],
    )

    assert track_result.steps == 4
    assert track_result.iterations == 500
    assert track_result.stop_reason.kind == "budget"
    _assert_artifact(track_artifact, adapter="track_a")
    assert track_artifact["final_state"] == [str(e) for e in track_result.state.objects]
    assert track_artifact["provenance"] == track_result.state.history

    assert puzzle_result.state == GOAL
    assert puzzle_result.steps == 2
    assert puzzle_result.iterations == 2
    assert puzzle_result.stop_reason.kind == "terminal"
    _assert_artifact(puzzle_artifact, adapter="8puzzle")
    assert puzzle_artifact["final_state"] == list(GOAL)
    assert puzzle_artifact["provenance"] == [
        [list(state), action, list(next_state)]
        for state, action, next_state in puzzle_adapter.history
    ]
