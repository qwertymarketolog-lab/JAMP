"""P24-B raw delta calculation and deterministic classification."""
from __future__ import annotations

from typing import Any

STAGE_DELTA_THRESHOLD_SEC = 1e-6


def _stage_deltas(baseline: dict[str, Any], result: dict[str, Any]) -> dict[str, float]:
    base = baseline.get("stages", {})
    current = result.get("stages", {})
    keys = set(base) | set(current)
    return {key: float(current.get(key, 0.0)) - float(base.get(key, 0.0)) for key in keys}


def _integrity_preserved(baseline: dict[str, Any], result: dict[str, Any]) -> bool:
    base_replay = baseline.get("replay_result", {})
    replay = result.get("replay_result", {})
    return (
        result.get("target_hash") == baseline.get("target_hash")
        and replay.get("state_hash") == base_replay.get("state_hash")
        and replay.get("lineage") == base_replay.get("lineage")
    )


def classify_ablation(
    factor_id: str,
    baseline: dict[str, Any],
    ablation_res: dict[str, Any],
) -> dict[str, Any]:
    """Classify only after execution; integrity failure is never SUPPORT."""
    if ablation_res.get("status") != "OK":
        return {
            "classification": "INCONCLUSIVE",
            "reason": "Execution status non-OK",
            "raw_delta": None,
            "threshold": STAGE_DELTA_THRESHOLD_SEC,
            "threshold_exceeded": False,
        }

    stage_deltas = _stage_deltas(baseline, ablation_res)
    integrity = _integrity_preserved(baseline, ablation_res)
    base_score = baseline.get("score")
    score = ablation_res.get("score")
    score_delta = score - base_score if base_score is not None and score is not None else None

    if factor_id == "F6":
        classification = "SUPPORTED" if integrity else "FALSIFIED"
        reason = "Semantic identity preserved" if integrity else "Semantic identity drift detected"
        raw_delta = None
        exceeded = False
    elif not integrity:
        classification = "INCONCLUSIVE"
        reason = "State/lineage integrity broken during factor intervention"
        raw_delta = score_delta
        exceeded = False
    elif factor_id in {"F1", "F2", "F4"}:
        changed = score_delta is not None and score_delta != 0
        classification = "SUPPORTED" if changed else "FALSIFIED"
        reason = "Primary outcome changed" if changed else "Primary outcome invariant under factor removal"
        raw_delta = score_delta
        exceeded = abs(score_delta) > STAGE_DELTA_THRESHOLD_SEC if score_delta is not None else False
    elif factor_id in {"F3", "F5"}:
        target = "verification_seconds" if factor_id == "F3" else "calibration"
        raw_delta = stage_deltas.get(target, 0.0)
        exceeded = abs(raw_delta) > STAGE_DELTA_THRESHOLD_SEC
        classification = "SUPPORTED" if exceeded else "FALSIFIED"
        reason = (
            f"Target stage delta ({raw_delta:.6e}s) exceeded threshold"
            if exceeded else f"Target stage invariant (raw_delta: {raw_delta:.6e}s)"
        )
    else:
        classification = "INCONCLUSIVE"
        reason = f"Unrecognized factor ID: {factor_id}"
        raw_delta = None
        exceeded = False

    return {
        "classification": classification,
        "reason": reason,
        "raw_delta": raw_delta,
        "threshold": STAGE_DELTA_THRESHOLD_SEC,
        "threshold_exceeded": exceeded,
        "score_delta": score_delta,
        "stage_deltas": stage_deltas,
        "integrity_preserved": integrity,
    }
