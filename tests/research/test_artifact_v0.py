from __future__ import annotations

import json
from types import SimpleNamespace

from scripts.artifact_v0 import serialize_run_result


def _result():
    return SimpleNamespace(
        steps=2,
        iterations=2,
        stop_reason=SimpleNamespace(kind="terminal", detail=""),
    )


def test_artifact_v0_serializes_two_opaque_domain_shapes():
    cases = [
        (
            "track-a",
            ["Expr(a)", "Expr(b)"],
            [{"step": 1, "op": "derive", "parents": [0], "expr": "Expr(b)"}],
        ),
        (
            "8puzzle",
            [1, 2, 3, 4, 5, 6, 7, 8, 0],
            [
                {
                    "state": [1, 2, 3, 4, 5, 6, 0, 7, 8],
                    "action": "RIGHT",
                    "next": [1, 2, 3, 4, 5, 6, 7, 0, 8],
                }
            ],
        ),
    ]

    for adapter, final_state, provenance in cases:
        artifact = serialize_run_result(
            _result(), adapter, final_state, provenance
        )
        restored = json.loads(json.dumps(artifact, ensure_ascii=False))
        assert restored == artifact
        assert restored["artifact_version"] == "v0"
        assert restored["adapter"] == adapter
        assert restored["run_result"]["steps"] == 2
        assert restored["final_state"] == final_state
        assert restored["provenance"] == provenance


def test_adapter_contract_is_optional_and_independent():
    artifact = serialize_run_result(
        _result(), "8puzzle", [1, 2, 3], [], adapter_contract="example-v1"
    )
    assert artifact["artifact_version"] == "v0"
    assert artifact["adapter_contract"] == "example-v1"
