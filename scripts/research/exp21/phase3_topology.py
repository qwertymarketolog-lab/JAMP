"""EXP-21 Phase 3 paired CPU-topology execution harness."""
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import random
import socket
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation
from research.exp21.phase3_contract import (
    ALPHA,
    EXPERIMENT_ID,
    PHASE,
    REQUIRED_PAIRS,
    WORKLOAD_DEFINITION_HASH,
    WORKLOAD_SPEC_ID,
    validate_artifact,
)

SEED = 2103
EDGE_COUNT = 20_000


class TopologyUnavailable(RuntimeError):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _topology(cpu: int) -> dict:
    root = Path(f"/sys/devices/system/cpu/cpu{cpu}/topology")
    if not root.exists():
        raise TopologyUnavailable(f"missing topology directory for cpu {cpu}")
    siblings = tuple(
        sorted(
            int(x)
            for x in _read(root / "thread_siblings_list")
            .replace("-", ",")
            .split(",")
            if x.strip().isdigit()
        )
    )
    return {
        "package": _read(root / "physical_package_id"),
        "core": _read(root / "core_id"),
        "thread": cpu,
        "sibling": list(siblings),
    }


def _sibling_pair(allowed: set[int]) -> tuple[int, int]:
    for cpu in sorted(allowed):
        info = _topology(cpu)
        for sibling in info["sibling"]:
            if sibling != cpu and sibling in allowed:
                return cpu, sibling
    raise TopologyUnavailable("no verified SMT sibling CPU pair in allowed affinity")


def _workload() -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(EDGE_COUNT // 2)
    ]
    edges += [
        ObservationRelation(
            str(i), str(i + EDGE_COUNT // 2), "adjacent", {}
        )
        for i in range(EDGE_COUNT // 2)
    ]
    return ObservationAdjacencyGraph(edges)


def _measure(
    cpu: int, pair_id: int, condition: str, target_commit: str
) -> dict:
    original = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, {cpu})
    try:
        after_affinity = sorted(os.sched_getaffinity(0))
        placement = _topology(cpu)
        if after_affinity != [cpu]:
            raise TopologyUnavailable(
                f"affinity verification failed for cpu {cpu}"
            )
        gc.collect()
        g0 = gc.get_stats()[2]["collections"]
        c0 = time.process_time_ns()
        w0 = time.perf_counter_ns()
        graph = _workload()
        graph.is_acyclic()
        wall_ms = (time.perf_counter_ns() - w0) / 1_000_000
        cpu_ms = (time.process_time_ns() - c0) / 1_000_000
        g1 = gc.get_stats()[2]["collections"]
        return {
            "experiment_id": EXPERIMENT_ID,
            "phase": PHASE,
            "target_commit": target_commit,
            "workload_spec_id": WORKLOAD_SPEC_ID,
            "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
            "experiment_seed": SEED,
            "pair_id": f"{pair_id:03d}",
            "condition": condition,
            "timestamp": datetime.now(UTC).isoformat(),
            "runner_name": socket.gethostname(),
            "runner_os": platform.system(),
            "runner_arch": platform.machine(),
            "kernel": platform.release(),
            "python_version": platform.python_version(),
            "cpu_count_visible": os.cpu_count(),
            "cpu_affinity_before": original,
            "cpu_affinity_after": after_affinity,
            "placement_before": _topology(original[0]),
            "placement_after": placement,
            "topology_package": placement["package"],
            "topology_core": placement["core"],
            "topology_thread": placement["thread"],
            "topology_sibling": placement["sibling"],
            "topology_verified": True,
            "affinity_verified": True,
            "wall_ms": wall_ms,
            "cpu_ms": cpu_ms,
            "non_cpu_delta_ms": wall_ms - cpu_ms,
            "gc_enabled": gc.isenabled(),
            "gc_gen2_collections": g1 - g0,
        }
    finally:
        os.sched_setaffinity(0, set(original))


def _inconclusive(
    target_commit: str, pairs: int, errors: list[str]
) -> dict:
    return {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": target_commit,
        "n_pairs": pairs,
        "alpha": ALPHA,
        "wilcoxon_p": float("nan"),
        "median_delta_ms": float("nan"),
        "status": "INCONCLUSIVE",
        "observations": [],
        "errors": errors,
    }


def run(pairs: int, target_commit: str, output: Path) -> int:
    if pairs != REQUIRED_PAIRS:
        raise ValueError(
            f"Phase 3 requires exactly {REQUIRED_PAIRS} pairs"
        )
    if platform.system() != "Linux":
        artifact = _inconclusive(
            target_commit, pairs, ["linux_required_for_topology_verification"]
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(artifact, indent=2), encoding="utf-8"
        )
        return 0

    allowed = set(os.sched_getaffinity(0))
    try:
        cpu_a, cpu_b = _sibling_pair(allowed)
        topo_a, topo_b = _topology(cpu_a), _topology(cpu_b)
        if (
            topo_a["package"] != topo_b["package"]
            or topo_a["core"] != topo_b["core"]
        ):
            raise TopologyUnavailable(
                "selected CPUs are not verified SMT siblings"
            )
    except TopologyUnavailable as exc:
        artifact = _inconclusive(target_commit, pairs, [str(exc)])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(artifact, indent=2), encoding="utf-8"
        )
        return 0

    rng = random.Random(SEED)
    observations = []
    for pair in range(1, pairs + 1):
        conditions = [("CONTROL", cpu_a), ("TOPOLOGY_TREATMENT", cpu_b)]
        rng.shuffle(conditions)
        for condition, cpu in conditions:
            observations.append(
                _measure(cpu, pair, condition, target_commit)
            )

    by_pair = {}
    for item in observations:
        by_pair.setdefault(item["pair_id"], {})[item["condition"]] = item["wall_ms"]
    deltas = [
        value["TOPOLOGY_TREATMENT"] - value["CONTROL"]
        for value in by_pair.values()
    ]
    try:
        from scipy.stats import wilcoxon

        p = float(
            wilcoxon(
                deltas, alternative="two-sided", method="auto"
            ).pvalue
        )
        status = (
            "TOPOLOGY_EFFECT_SUPPORTED"
            if p < ALPHA
            else "TOPOLOGY_EFFECT_NOT_SUPPORTED"
        )
        errors = []
    except ImportError:
        p = float("nan")
        status = "INCONCLUSIVE"
        errors = ["scipy_unavailable"]

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "phase": PHASE,
        "target_commit": target_commit,
        "workload_spec_id": WORKLOAD_SPEC_ID,
        "workload_definition_hash": WORKLOAD_DEFINITION_HASH,
        "experiment_seed": SEED,
        "n_pairs": pairs,
        "alpha": ALPHA,
        "wilcoxon_p": p,
        "median_delta_ms": statistics.median(deltas),
        "status": status,
        "cpu_a": cpu_a,
        "cpu_b": cpu_b,
        "topology_a": topo_a,
        "topology_b": topo_b,
        "observations": observations,
        "errors": errors,
    }
    valid, validation_errors = validate_artifact(
        artifact, expected_target_commit=target_commit
    )
    if not valid:
        artifact["status"] = "INCONCLUSIVE"
        artifact["validation_errors"] = validation_errors
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=REQUIRED_PAIRS)
    parser.add_argument("--target-commit", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/research/exp21_phase3_topology_results.json"),
    )
    args = parser.parse_args()
    return run(args.pairs, args.target_commit, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
