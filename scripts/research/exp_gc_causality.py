"""Controlled GC-causality experiment for the canonical EXP-21 G4 workload.

Research-only. The measured region is deliberately identical to Phase 0:
graph construction is untimed; only is_acyclic() and reachable("0") are timed.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

WORKLOAD_SPEC_ID = "EXP-21-PHASE0-G4-CANONICAL-V1"
EXPERIMENT_SEED = int(os.getenv("EXPERIMENT_SEED", "1905"))
DEFAULT_N = 30

CANONICAL_G4_WORKLOAD_CODE = """from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

edges = [(str(i), str(i + 1)) for i in range(10_000)]
edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
relations = tuple(
    ObservationRelation(source, target, "adjacent", {}) for source, target in edges
)
g = ObservationAdjacencyGraph(relations)

gc_gen2_before = gc.get_stats()[2]["collections"]
wall_start = time.perf_counter()
cpu_start = time.process_time()
_ = g.is_acyclic()
_ = g.reachable("0")
cpu_end = time.process_time()
wall_end = time.perf_counter()
gc_gen2_after = gc.get_stats()[2]["collections"]
"""

WORKLOAD_DEFINITION_HASH = hashlib.sha256(
    CANONICAL_G4_WORKLOAD_CODE.encode("utf-8")
).hexdigest()


def resolve_target_commit() -> str:
    env_sha = os.getenv("TARGET_COMMIT", "").strip()
    if env_sha:
        if len(env_sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in env_sha):
            raise RuntimeError("TARGET_COMMIT must be a 40-character hexadecimal SHA")
        actual = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if actual != env_sha:
            raise RuntimeError(
                f"TARGET_COMMIT mismatch: expected {env_sha}, actual {actual}"
            )
        return env_sha

    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
    ).strip()
    if len(actual) != 40:
        raise RuntimeError("git rev-parse HEAD returned an invalid SHA")
    return actual


def prepare_neutral_gc_state() -> None:
    gc.enable()
    gc.collect(2)


def build_canonical_graph() -> ObservationAdjacencyGraph:
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {}) for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


def execute_g4_workload() -> tuple[float, float, float, int]:
    prepare_neutral_gc_state()
    graph = build_canonical_graph()

    gen2_before = gc.get_stats()[2]["collections"]
    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    _ = graph.is_acyclic()
    _ = graph.reachable("0")

    cpu_end = time.process_time()
    wall_end = time.perf_counter()
    gen2_after = gc.get_stats()[2]["collections"]

    wall_ms = (wall_end - wall_start) * 1000.0
    cpu_ms = (cpu_end - cpu_start) * 1000.0
    return wall_ms, cpu_ms, wall_ms - cpu_ms, gen2_after - gen2_before


def run_pair(rng: random.Random) -> dict[str, object]:
    conditions = ["BASELINE", "DISABLED_HOTPATH", "THRESHOLD_HIGH"]
    rng.shuffle(conditions)
    observations: dict[str, object] = {}

    old_thresholds = gc.get_threshold()
    try:
        for condition in conditions:
            if condition == "BASELINE":
                gc.enable()
                wall_ms, cpu_ms, non_cpu_ms, gen2 = execute_g4_workload()
            elif condition == "DISABLED_HOTPATH":
                gc.disable()
                wall_ms, cpu_ms, non_cpu_ms, gen2 = execute_g4_workload()
            elif condition == "THRESHOLD_HIGH":
                gc.enable()
                gc.set_threshold(700_000, 1_000, 1_000)
                wall_ms, cpu_ms, non_cpu_ms, gen2 = execute_g4_workload()
            observations[condition] = {
                "wall_ms": wall_ms,
                "cpu_ms": cpu_ms,
                "non_cpu_delta_ms": non_cpu_ms,
                "n_gc_gen2": gen2,
            }
    finally:
        gc.set_threshold(*old_thresholds)
        gc.enable()

    return observations


def analyse(pairs: list[dict[str, object]]) -> dict[str, object]:
    try:
        from scipy import __version__ as scipy_version
        from scipy.stats import wilcoxon
    except Exception as exc:
        return {
            "verdict": "ANALYSIS_UNAVAILABLE",
            "analysis_error": f"SciPy unavailable: {exc}",
        }

    deltas = [
        float(pair["DISABLED_HOTPATH"]["wall_ms"])
        - float(pair["BASELINE"]["wall_ms"])
        for pair in pairs
    ]
    median_delta = statistics.median(deltas)

    try:
        result = wilcoxon(
            deltas,
            zero_method="wilcox",
            alternative="two-sided",
        )
    except Exception as exc:
        return {
            "verdict": "ANALYSIS_UNAVAILABLE",
            "analysis_error": f"Wilcoxon failed: {exc}",
            "deltas_ms": deltas,
        }

    p_value = float(result.pvalue)
    if p_value < 0.01 and median_delta < 0:
        verdict = "GC_ASSOCIATED_LATENCY_EFFECT"
    else:
        verdict = "NO_REPRODUCIBLE_GC_LATENCY_EFFECT"

    return {
        "verdict": verdict,
        "scipy_version": scipy_version,
        "wilcoxon": {
            "statistic": float(result.statistic),
            "p_value": p_value,
            "zero_method": "wilcox",
            "alternative": "two-sided",
        },
        "median_delta_ms": median_delta,
        "deltas_ms": deltas,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/research/exp_gc_causality_results.json"),
    )
    args = parser.parse_args()

    if args.n < 1:
        raise SystemExit("--n must be >= 1")

    target_commit = resolve_target_commit()
    pairs: list[dict[str, object]] = []
    rng = random.Random(EXPERIMENT_SEED)

    for _ in range(args.n):
        pairs.append(run_pair(rng))

    analysis = analyse(pairs)
    payload = {
        "experiment": "EXP-GC-1B",
        "status": analysis["verdict"],
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_sha256": WORKLOAD_DEFINITION_HASH,
        "target_commit": target_commit,
        "experiment_seed": EXPERIMENT_SEED,
        "n_pairs": args.n,
        "timed_region": ["g.is_acyclic()", 'g.reachable("0")'],
        "gc_gen2_telemetry": "gc.get_stats()[2][\"collections\"] delta",
        "conditions": ["BASELINE", "DISABLED_HOTPATH", "THRESHOLD_HIGH"],
        "pairs": pairs,
        "analysis": analysis,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(json.dumps({
        "status": analysis["verdict"],
        "target_commit": target_commit,
        "workload_definition_sha256": WORKLOAD_DEFINITION_HASH,
        "n_pairs": args.n,
    }, indent=2))

    return 1 if analysis["verdict"] == "ANALYSIS_UNAVAILABLE" else 0


if __name__ == "__main__":
    # The repository root is required for research.exp19 imports.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
