"""EXP-19.MEM-ATTR — RED attribution benchmark.

Measurement only: no memory/latency thresholds and no production/runtime changes.
"""

from __future__ import annotations

import gc
import json
import os
import random
import statistics
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

import psutil

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


PROFILES = ("single", "mixed", "rare", "dominant", "empty", "near-complete")
V = 10_000
E = 20_000
SEED = 42
SAMPLES = 10
WARMUP = 1
TARGET_RELATION = "DEP"
ARTIFACT_PATH = Path("artifacts/exp19-mem-attr/benchmark-memory-attribution.json")


@dataclass(frozen=True)
class PhaseSample:
    elapsed_ns: int
    current_bytes: int
    peak_bytes: int
    rss_before_bytes: int
    rss_after_bytes: int
    snapshot_diff: tuple[dict[str, int | str], ...]

    @property
    def rss_delta_bytes(self) -> int:
        return self.rss_after_bytes - self.rss_before_bytes


def _rss_bytes() -> int:
    return psutil.Process(os.getpid()).memory_info().rss


def _relation_types(profile: str, index: int) -> str:
    if profile == "single":
        return TARGET_RELATION
    if profile == "empty":
        return "OTHER"
    if profile == "rare":
        return TARGET_RELATION if index % 100 == 0 else "OTHER"
    if profile == "dominant":
        return TARGET_RELATION if index % 100 != 0 else "OTHER"
    if profile == "mixed":
        return TARGET_RELATION if index % 2 == 0 else "OTHER"
    if profile == "near-complete":
        return TARGET_RELATION if index < E - 1 else "OTHER"
    raise ValueError(f"Unknown profile: {profile}")


def build_relations(profile: str) -> tuple[ObservationRelation, ...]:
    rng = random.Random(SEED)
    relations: list[ObservationRelation] = []
    seen: set[tuple[int, int, str]] = set()

    while len(relations) < E:
        source = rng.randrange(V)
        target = rng.randrange(V)
        if source == target:
            continue
        relation_type = _relation_types(profile, len(relations))
        key = (source, target, relation_type)
        if key in seen:
            continue
        seen.add(key)
        relations.append(
            ObservationRelation(
                source_id=f"o{source}",
                target_id=f"o{target}",
                relation_type=relation_type,
                params={"profile": profile},
            )
        )
    return tuple(relations)


def build_graph(profile: str) -> tuple[ObservationAdjacencyGraph, tuple[ObservationRelation, ...]]:
    relations = build_relations(profile)
    return ObservationAdjacencyGraph(relations), relations


def _snapshot_diff(before: tracemalloc.Snapshot, after: tracemalloc.Snapshot) -> tuple[dict[str, int | str], ...]:
    rows: list[dict[str, int | str]] = []
    for stat in after.compare_to(before, "lineno")[:12]:
        frame = stat.traceback[0]
        rows.append(
            {
                "file": str(frame.filename),
                "line": frame.lineno,
                "size_diff_bytes": stat.size_diff,
                "count_diff": stat.count_diff,
            }
        )
    return tuple(rows)


def _measure(operation) -> PhaseSample:
    gc.collect()
    tracemalloc.start()
    tracemalloc.reset_peak()
    rss_before = _rss_bytes()
    before = tracemalloc.take_snapshot()
    started = perf_counter_ns()
    operation()
    elapsed = perf_counter_ns() - started
    after = tracemalloc.take_snapshot()
    current, peak = tracemalloc.get_traced_memory()
    rss_after = _rss_bytes()
    diff = _snapshot_diff(before, after)
    tracemalloc.stop()
    return PhaseSample(
        elapsed_ns=elapsed,
        current_bytes=current,
        peak_bytes=peak,
        rss_before_bytes=rss_before,
        rss_after_bytes=rss_after,
        snapshot_diff=diff,
    )


def _warmup(operation) -> None:
    for _ in range(WARMUP):
        operation()


def _phase_result(samples: list[PhaseSample]) -> dict:
    return {
        "samples": [
            {
                "elapsed_ns": s.elapsed_ns,
                "current_bytes": s.current_bytes,
                "peak_bytes": s.peak_bytes,
                "rss_before_bytes": s.rss_before_bytes,
                "rss_after_bytes": s.rss_after_bytes,
                "rss_delta_bytes": s.rss_delta_bytes,
                "snapshot_diff": list(s.snapshot_diff),
            }
            for s in samples
        ],
        "median_elapsed_ns": int(statistics.median(s.elapsed_ns for s in samples)),
        "median_current_bytes": int(statistics.median(s.current_bytes for s in samples)),
        "median_peak_bytes": int(statistics.median(s.peak_bytes for s in samples)),
        "median_rss_delta_bytes": int(statistics.median(s.rss_delta_bytes for s in samples)),
    }


def collect_profile(profile: str) -> dict:
    graph, relations = build_graph(profile)
    target_count = sum(r.relation_type == TARGET_RELATION for r in relations)

    filtered_edges = {
        key: relation
        for key, relation in graph._edges.items()
        if relation.relation_type == TARGET_RELATION
    }

    def edge_filter() -> dict:
        return {
            key: relation
            for key, relation in graph._edges.items()
            if relation.relation_type == TARGET_RELATION
        }

    def reconstruct() -> ObservationAdjacencyGraph:
        return ObservationAdjacencyGraph(tuple(filtered_edges.values()))

    def end_to_end() -> ObservationAdjacencyGraph:
        return graph.subgraph_view(TARGET_RELATION)

    _warmup(edge_filter)
    _warmup(reconstruct)
    _warmup(end_to_end)

    edge_samples: list[PhaseSample] = []
    reconstruction_samples: list[PhaseSample] = []
    end_to_end_samples: list[PhaseSample] = []

    for _ in range(SAMPLES):
        holder: dict[str, object] = {}
        sample = _measure(lambda: holder.setdefault("filtered_edges", edge_filter()))
        edge_samples.append(sample)
        del holder

    for _ in range(SAMPLES):
        holder: dict[str, object] = {}
        sample = _measure(lambda: holder.setdefault("graph", reconstruct()))
        reconstruction_samples.append(sample)
        del holder

    for _ in range(SAMPLES):
        holder: dict[str, object] = {}
        sample = _measure(lambda: holder.setdefault("view", end_to_end()))
        end_to_end_samples.append(sample)
        del holder

    reconstructed = reconstruct()
    view = end_to_end()

    return {
        "profile": profile,
        "V": V,
        "E": E,
        "seed": SEED,
        "target_relation": TARGET_RELATION,
        "target_edge_count": target_count,
        "phases": {
            "edge_filtering": _phase_result(edge_samples),
            "graph_reconstruction": _phase_result(reconstruction_samples),
            "subgraph_view_end_to_end": _phase_result(end_to_end_samples),
        },
        "reconstruction_structures": {
            "node_count": reconstructed._v_count,
            "edge_count": len(reconstructed._edges),
            "node_to_idx_count": len(reconstructed._node_to_idx),
            "idx_to_node_count": len(reconstructed._idx_to_node),
            "adj_int_rows": len(reconstructed._adj_int),
            "adj_int_entries": sum(len(row) for row in reconstructed._adj_int),
        },
        "control": {
            "end_to_end_target_edge_count": len(view._edges),
            "phase_sum_median_elapsed_ns": (
                _phase_result(edge_samples)["median_elapsed_ns"]
                + _phase_result(reconstruction_samples)["median_elapsed_ns"]
            ),
        },
    }


def build_artifact() -> dict:
    profiles = [collect_profile(profile) for profile in PROFILES]
    return {
        "protocol": "MEM-ATTR-v0",
        "status": "MEASURED",
        "V": V,
        "E": E,
        "seed": SEED,
        "profiles": profiles,
        "primary_dense_profiles": ["single", "near-complete"],
        "measurement": {
            "timing": "time.perf_counter_ns",
            "memory": "tracemalloc snapshots and current/peak bytes",
            "rss": "process RSS before/after/delta",
            "snapshot_diff": "tracemalloc Snapshot.compare_to(..., 'lineno')",
            "phase_1": "filtered_edges dict comprehension",
            "phase_2": "ObservationAdjacencyGraph(tuple(filtered_edges.values()))",
            "phase_3": "graph.subgraph_view(TARGET_RELATION)",
        },
        "thresholds": None,
        "production_changes": 0,
        "runtime_changes": 0,
    }


def test_attribution_harness_schema() -> None:
    artifact = build_artifact()
    assert artifact["protocol"] == "MEM-ATTR-v0"
    assert artifact["thresholds"] is None
    assert artifact["production_changes"] == 0
    assert artifact["runtime_changes"] == 0
    assert [p["profile"] for p in artifact["profiles"]] == list(PROFILES)
    for profile in artifact["profiles"]:
        assert profile["phases"]["edge_filtering"]["samples"]
        assert profile["phases"]["graph_reconstruction"]["samples"]
        assert profile["phases"]["subgraph_view_end_to_end"]["samples"]
        assert profile["control"]["end_to_end_target_edge_count"] == profile["target_edge_count"]


def test_attribution_artifact_is_serializable(tmp_path: Path) -> None:
    artifact = build_artifact()
    output = tmp_path / "benchmark-memory-attribution.json"
    output.write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    assert json.loads(output.read_text(encoding="utf-8"))["protocol"] == "MEM-ATTR-v0"
