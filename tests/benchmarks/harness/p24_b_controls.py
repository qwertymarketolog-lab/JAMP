"""Semantic zero-drift verification for the P24-B F6 control."""
from __future__ import annotations

from typing import Any


_STAGE_KEYS = ("restore_seconds", "scoring_seconds", "replay_seconds", "verification_seconds")


def evaluate_f6_semantic_gate(
    baseline_payload: dict[str, Any],
    control_payload: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """Check semantic identity while reporting physical timing deltas separately."""
    base_replay = baseline_payload.get("replay_result", {})
    ctrl_replay = control_payload.get("replay_result", {})
    integrity_pass = (
        control_payload.get("status") == "OK"
        and control_payload.get("target_hash") == baseline_payload.get("target_hash")
        and ctrl_replay.get("state_hash") == base_replay.get("state_hash")
        and ctrl_replay.get("lineage") == base_replay.get("lineage")
    )

    base_stages = baseline_payload.get("stages", {})
    ctrl_stages = control_payload.get("stages", {})
    stage_deltas: dict[str, dict[str, float]] = {}
    for stage in _STAGE_KEYS:
        base_time = float(base_stages.get(stage, 0.0))
        ctrl_time = float(ctrl_stages.get(stage, 0.0))
        delta = ctrl_time - base_time
        stage_deltas[stage] = {
            "baseline": base_time,
            "control": ctrl_time,
            "raw_delta": delta,
            "rel_diff": abs(delta) / base_time if base_time > 0 else 0.0,
        }

    return integrity_pass, {
        "integrity_passed": integrity_pass,
        "stage_deltas": stage_deltas,
    }
