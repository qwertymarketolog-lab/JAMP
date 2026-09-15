from __future__ import annotations

import json
from typing import Any

from jamp.run import run
from tests.research.puzzle8_run_adapter import Puzzle8Adapter


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def build_neutral_artifact(adapter: Puzzle8Adapter) -> dict[str, Any]:
    result = run(adapter)
    artifact = {
        "contract": "run-v0.3",
        "adapter": "8puzzle",
        "run_result": {
            "steps": result.steps,
            "iterations": result.iterations,
            "stop_reason": {
                "kind": result.stop_reason.kind,
                "detail": result.stop_reason.detail,
            },
        },
        "final_state": _jsonable(result.state),
        "provenance": _jsonable(adapter.history),
    }
    json.dumps(artifact, ensure_ascii=False)
    return artifact


if __name__ == "__main__":
    artifact = build_neutral_artifact(Puzzle8Adapter())
    print(json.dumps(artifact, indent=2, ensure_ascii=False))
