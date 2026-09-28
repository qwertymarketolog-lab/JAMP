"""Aggregate EXP-22 Phase 1B matrix artifacts without discarding raw observations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPERIMENT_ID = "EXP-22-PHASE1B-INTER-RUN-PROFILING"
CORE_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
WORKLOAD_HASH = "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
G4_THRESHOLD_MS = 15.0


def _summary(values: list[float]) -> dict[str, float]:
    values = sorted(values)
    if not values:
        raise ValueError("empty_values")
    def percentile(p: float) -> float:
        index = max(0, min(len(values) - 1, int((p * len(values) + 0.999999999) - 1)))
        return values[index]
    import statistics
    return {
        "min": values[0],
        "median": statistics.median(values),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
        "max": values[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--target-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    files = sorted(args.input_dir.glob("exp22_phase1b_run_*.json"))
    if len(files) != 15:
        errors.append(f"expected_15_artifacts_got_{len(files)}")

    runs: list[dict[str, Any]] = []
    all_observations: list[dict[str, Any]] = []

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("target_commit") != args.target_commit:
            errors.append(f"{path.name}:target_commit_mismatch")
        if data.get("core_blob") != CORE_BLOB:
            errors.append(f"{path.name}:core_blob_mismatch")
        if data.get("workload_spec_id") != WORKLOAD_SPEC_ID:
            errors.append(f"{path.name}:workload_spec_mismatch")
        if data.get("workload_definition_hash") != WORKLOAD_HASH:
            errors.append(f"{path.name}:workload_hash_mismatch")
        if data.get("status") != "VERIFIED":
            errors.append(f"{path.name}:status_not_verified")

        observations = data.get("raw_observations", [])
        if len(observations) != 50:
            errors.append(f"{path.name}:expected_50_observations_got_{len(observations)}")

        index = int(path.stem.rsplit("_", 1)[-1])
        environment = data.get("environment_metadata", {})
        wall = [float(o["wall_ms"]) for o in observations]
        delta = [float(o["non_cpu_delta_ms"]) for o in observations]
        failures = sum(v > G4_THRESHOLD_MS for v in wall)

        runs.append({
            "run_index": index,
            "environment_fingerprint": {
                "runner_name": environment.get("runner_name"),
                "runner_os": environment.get("runner_os"),
                "runner_arch": environment.get("runner_arch"),
                "cpu_model": environment.get("cpu_model"),
                "kernel": environment.get("kernel"),
                "cpu_affinity": environment.get("cpu_affinity"),
            },
            "stats": {
                "wall_ms": _summary(wall),
                "non_cpu_delta_ms": _summary(delta),
                "fail_count_gt_15ms": failures,
            },
            "raw_observations": observations,
        })
        all_observations.extend(
            {**o, "run_index": index} for o in observations
        )

    if len(runs) != 15:
        errors.append("run_count_not_15")
    if len(all_observations) != 750:
        errors.append(f"expected_750_observations_got_{len(all_observations)}")

    wall = [float(o["wall_ms"]) for o in all_observations]
    composite = {
        "experiment_id": EXPERIMENT_ID,
        "target_commit": args.target_commit,
        "core_blob": CORE_BLOB,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_HASH,
        "total_runs": len(runs),
        "total_observations": len(all_observations),
        "runs": runs,
        "inter_run_summary": {
            "global_wall_ms": _summary(wall) if wall else {},
            "total_g4_failures": sum(v > G4_THRESHOLD_MS for v in wall),
            "failure_rate": (
                sum(v > G4_THRESHOLD_MS for v in wall) / len(wall) if wall else 0.0
            ),
        },
        "epistemic_classification": {
            "measurement_boundary": "VERIFIED" if not errors else "INCONCLUSIVE",
            "execution_identity": "VERIFIED" if not errors else "INCONCLUSIVE",
            "frozen_core": "VERIFIED" if not errors else "INCONCLUSIVE",
            "inter_run_variability": "OBSERVED" if not errors else "INCONCLUSIVE",
            "g4_root_cause": "UNKNOWN",
        },
        "validation_errors": errors,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(composite, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
