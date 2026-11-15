from __future__ import annotations
import argparse, datetime as dt, gc, json, os, platform, statistics, subprocess, time
from pathlib import Path
from typing import Any
from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation
from research.exp21.phase2_contract import ALPHA, EXPERIMENT_ID, REQUIRED_PAIRS, WORKLOAD_DEFINITION_HASH, WORKLOAD_SPEC_ID, validate_artifact

SEED = os.environ.get("EXP21_EXPERIMENT_SEED", "EXP21-PHASE2-SCHEDULING-V1")
TARGET = os.environ.get("EXP21_TARGET_COMMIT", "")

def affinity() -> list[int]:
    if not hasattr(os, "sched_getaffinity"):
        raise RuntimeError("cpu_affinity_unsupported")
    return sorted(os.sched_getaffinity(0))

def set_affinity(cpus: list[int]) -> None:
    if not hasattr(os, "sched_setaffinity"):
        raise RuntimeError("cpu_affinity_unsupported")
    os.sched_setaffinity(0, set(cpus))

def workload() -> ObservationAdjacencyGraph:
    edges = [ObservationRelation(str(i), str(i + 1), "adjacent", {}) for i in range(10_000)]
    edges.extend(ObservationRelation(str(i), str(i + 10_000), "adjacent", {}) for i in range(10_000))
    return ObservationAdjacencyGraph(tuple(edges))

def measure(pair: str, condition: str) -> dict[str, Any]:
    before = affinity()
    cpu = before[0]
    if condition == "CPU_AFFINITY":
        set_affinity([cpu])
    after = affinity()
    verified = after == before if condition == "CONTROL" else after == [cpu]
    if not verified:
        raise RuntimeError("affinity_verification_failed:" + condition)
    gc_before = gc.get_stats()[2]["collections"]
    wall0, cpu0 = time.perf_counter(), time.process_time()
    g = workload()
    if not g.is_acyclic():
        raise RuntimeError("canonical_graph_acyclicity_failed")
    g.reachable("0")
    wall_ms = (time.perf_counter() - wall0) * 1000
    cpu_ms = (time.process_time() - cpu0) * 1000
    return {
        "experiment_id": EXPERIMENT_ID, "phase": 2, "pair_id": pair, "condition": condition,
        "target_commit": TARGET, "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH, "experiment_seed": SEED,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runner_name": os.environ.get("RUNNER_NAME", platform.node()), "runner_os": platform.system(),
        "runner_arch": platform.machine(), "kernel": platform.release(),
        "python_version": platform.python_version(), "cpu_count_visible": os.cpu_count(),
        "cpu_affinity_before": before, "cpu_affinity_after": after, "affinity_verified": verified,
        "wall_ms": wall_ms, "cpu_ms": cpu_ms, "non_cpu_delta_ms": wall_ms - cpu_ms,
        "gc_enabled": gc.isenabled(), "gc_gen2_collections": gc.get_stats()[2]["collections"] - gc_before,
    }

def run() -> dict[str, Any]:
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not TARGET or actual != TARGET:
        raise RuntimeError("target_commit_mismatch:expected=" + TARGET + ":actual=" + actual)
    original = affinity()
    observations, errors = [], []
    for i in range(1, REQUIRED_PAIRS + 1):
        pair = "P%02d" % i
        order = ("CONTROL", "CPU_AFFINITY") if i % 2 else ("CPU_AFFINITY", "CONTROL")
        for condition in order:
            try:
                observations.append(measure(pair, condition))
            except Exception as exc:
                errors.append("pair_%s:%s:%s:%s" % (pair, condition, type(exc).__name__, exc))
                break
            finally:
                try:
                    set_affinity(original)
                except Exception as exc:
                    errors.append("restore:%s:%s" % (type(exc).__name__, exc))
                    break
        if errors:
            break
    pairs: dict[str, dict[str, float]] = {}
    for obs in observations:
        pairs.setdefault(obs["pair_id"], {})[obs["condition"]] = obs["wall_ms"]
    deltas = [v["CPU_AFFINITY"] - v["CONTROL"] for v in pairs.values() if set(v) == {"CONTROL", "CPU_AFFINITY"}]
    p, status = None, "INCONCLUSIVE"
    if len(deltas) == REQUIRED_PAIRS and not errors:
        try:
            from scipy.stats import wilcoxon
            p = float(wilcoxon(deltas, alternative="two-sided", method="auto").pvalue)
            status = "SCHEDULING_EFFECT_SUPPORTED" if p < ALPHA else "SCHEDULING_EFFECT_NOT_SUPPORTED"
        except Exception as exc:
            errors.append("scipy:%s:%s" % (type(exc).__name__, exc))
    artifact = {
        "experiment_id": EXPERIMENT_ID, "phase": 2, "target_commit": TARGET,
        "workload_spec_id": WORKLOAD_SPEC_ID, "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": SEED, "n_pairs": len(deltas), "wilcoxon_p": p, "alpha": ALPHA,
        "median_delta_ms": statistics.median(deltas) if deltas else None, "status": status,
        "validation_errors": errors, "observations": observations,
    }
    ok, contract_errors = validate_artifact(artifact, expected_target_commit=TARGET)
    if not ok:
        artifact["status"] = "INCONCLUSIVE"
        artifact["validation_errors"] = sorted(set(errors + contract_errors))
    return artifact

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        artifact = run()
    except Exception as exc:
        artifact = {
            "experiment_id": EXPERIMENT_ID, "phase": 2, "target_commit": TARGET,
            "workload_spec_id": WORKLOAD_SPEC_ID, "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
            "experiment_seed": SEED, "n_pairs": 0, "wilcoxon_p": None, "alpha": ALPHA,
            "median_delta_ms": None, "status": "INCONCLUSIVE",
            "validation_errors": ["execution:%s:%s" % (type(exc).__name__, exc)], "observations": [],
        }
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    return 2 if artifact["status"] == "INCONCLUSIVE" else 0

if __name__ == "__main__":
    raise SystemExit(main())
