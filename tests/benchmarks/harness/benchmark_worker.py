"""Independent worker for P24-A telemetry and P24-B harness interventions."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from jamp.research.hypothesis_scoring import score_hypothesis
from jamp.research.replay import replay_state, verify_replay
from tests.benchmarks.harness.cold_replay_worker import _restore
from tests.benchmarks.harness.snapshot_schema import load_snapshot

CALIBRATION_RUNS = 1000


def _measure_null_overhead(runs: int = CALIBRATION_RUNS) -> dict[str, float | int]:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        pass
        samples.append(time.perf_counter() - started)
    return {"runs": runs, "min_seconds": min(samples), "mean_seconds": sum(samples) / len(samples), "max_seconds": max(samples)}


def _measure(call):
    started = time.perf_counter()
    value = call()
    return value, time.perf_counter() - started


def _parse_context(raw: str) -> dict[str, Any]:
    context = json.loads(raw)
    if not isinstance(context, dict):
        raise ValueError("ctx-json must contain a JSON object")
    return context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--target-hash", required=True)
    parser.add_argument("--hypothesis-index", type=int, default=0)
    parser.add_argument("--ctx-json", default="{}")
    args = parser.parse_args()
    ctx = _parse_context(args.ctx_json)

    calibration = {"runs": 0, "min_seconds": 0.0, "mean_seconds": 0.0, "max_seconds": 0.0}
    if not ctx.get("skip_calibration", False):
        calibration = _measure_null_overhead()

    restored, restore_seconds = _measure(lambda: _restore(load_snapshot(args.snapshot)))
    graph, ledger, hypotheses = restored
    if not 0 <= args.hypothesis_index < len(hypotheses):
        raise IndexError("hypothesis index is outside snapshot")
    hypothesis = hypotheses[args.hypothesis_index]

    replay_result, replay_seconds = _measure(lambda: replay_state(graph, args.target_hash))

    verification_seconds = 0.0
    verification_passed = None
    if not ctx.get("skip_verification", False):
        verification_passed, verification_seconds = _measure(lambda: verify_replay(graph, replay_result))

    scoring_seconds = 0.0
    score = None
    if not ctx.get("skip_scoring", False):
        score, scoring_seconds = _measure(lambda: score_hypothesis(hypothesis, ledger, graph))

    consumed = [key for key in (
        "lineage_override", "causal_chain_override", "skip_verification", "skip_scoring", "skip_calibration"
    ) if key in ctx]

    # F1/F2 are deliberately consumed at the harness boundary without fabricating
    # domain state. Their effect (or lack of effect) is therefore an observation.
    result = {
        "status": "OK",
        "consumed_overrides": consumed,
        "calibration": calibration,
        "stages": {
            "restore_seconds": restore_seconds,
            "replay_seconds": replay_seconds,
            "verification_seconds": verification_seconds,
            "scoring_seconds": scoring_seconds,
            "calibration_seconds": calibration.get("mean_seconds", 0.0),
        },
        "target_hash": args.target_hash,
        "hypothesis_index": args.hypothesis_index,
        "score": score,
        "verification_passed": verification_passed,
        "replay_result": replay_result.export(),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
