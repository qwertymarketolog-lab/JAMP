from __future__ import annotations

from typing import Any

from jamp.run import run
from scripts.artifact_v0 import serialize_run_result

from exp03_adapter import Exp03Adapter, SearchState
from exp03_graph import NODES


def _state_payload(state: SearchState) -> dict[str, Any]:
    return {
        "current": NODES[state.current].name,
        "frontier": [NODES[node_id].name for node_id in state.frontier],
        "visited": [NODES[node_id].name for node_id in state.visited],
    }


def _provenance(adapter: Exp03Adapter) -> list[dict[str, Any]]:
    return [
        {
            "step": index,
            "selected": NODES[selected].name,
            "before": _state_payload(before),
            "after": _state_payload(after),
        }
        for index, (before, selected, after) in enumerate(adapter.history, start=1)
    ]


def run_exp03() -> tuple[Any, dict[str, Any]]:
    adapter = Exp03Adapter()
    result = run(adapter)
    artifact = serialize_run_result(
        result,
        adapter="exp03-8puzzle-branching",
        final_state=_state_payload(result.state),
        provenance=_provenance(adapter),
    )
    return result, artifact
