"""EXP-19.MEM-OPT — OPT-1 ViewBuilder benchmark harness.

Research-only candidate proxy. No src/jamp changes and no performance threshold.
"""

from __future__ import annotations

import gc
import json
import os
import statistics
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
from types import MappingProxyType

import psutil

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

RELATION_TYPES = ("DEP", "REF", "DATA", "CTRL")
PROFILES = ("single", "mixed", "rare", "dominant", "empty", "near-complete")
SEED = 42
V = 10_000
E = 20_000
TARGET_RELATION = "CTRL"


def _relation_types(profile: str, count: int) -> list[str]:
    if profile == "single":
        return ["CTRL"] * count
    if profile == "mixed":
        return [RELATION_TYPES[index % len(RELATION_TYPES)] for index in range(count)]
    if profile == "rare":
        rare_count = max(1, count // 200)
        return ["CTRL"] * rare_count + ["DEP"] * (count - rare_count)
    if profile == "dominant":
        dominant_count = int(count * 0.96)
        return ["CTRL"] * dominant_count + [
            RELATION_TYPES[index % 3] for index in range(count - dominant_count)
        ]
    if profile == "empty":
        return ["DEP"] * count
    if profile == "near-complete":
        return [RELATION_TYPES[index % 2] for index in range(count)]
    raise ValueError(f"Unknown benchmark profile: {profile}")


def _edge_pairs(profile: str, vertices: int, edges: int, seed: int) -> list[tuple[int, int]]:
    import random

    rng = random.Random(seed)
    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    if profile == "near-complete":
        dense_vertices = max(200, min(vertices, 300))
        candidates = [
            (source, target)
            for source in range(dense_vertices)
            for target in range(source + 1, dense_vertices)
        ]
        rng.shuffle(candidates)
        pairs.extend(candidates[: min(edges, len(candidates))])
        seen.update(pairs)
    while len(pairs) < edges:
        source = rng.randrange(vertices - 1)
        target = rng.randrange(source + 1, vertices)
        pair = (source, target)
        if pair not in seen:
            seen.add(pair)
            pairs.append(pair)
    return pairs


def build_relations(profile: str) -> tuple[ObservationRelation, ...]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown benchmark profile: {profile}")
    pairs = _edge_pairs(profile, V, E, SEED)
    types = _relation_types(profile, E)
    return tuple(
        ObservationRelation(
            source_id=f"n{source:05d}",
            target_id=f"n{target:05d}",
            relation_type=relation_type,
            params={"seed": SEED, "ordinal": index},
        )
        for index, ((source, target), relation_type) in enumerate(
            zip(pairs, types, strict=True)
        )
    )


ARTIFACT_PATH = Path("artifacts/exp19-mem-opt/benchmark-memory-opt.json")
SAMPLES = 10
WARMUP = 1


class ViewBuilder:
    """Lightweight research proxy over a base graph and filtered edge mapping."""

    __slots__ = ("_base", "_edges")

    def __init__(self, base: ObservationAdjacencyGraph, relation_type: str) -> None:
        self._base = base
        self._edges = MappingProxyType(
            {
                key: relation
                for key, relation in base._edges.items()
                if relation.relation_type == relation_type
            }
        )

    def is_acyclic(self) -> bool:
        color: dict[str, int] = {}
        adjacency: dict[str, list[str]] = {}
        for relation in self._edges.values():
            adjacency.setdefault(relation.source_id, []).append(relation.target_id)

        def visit(node: str) -> bool:
            state = color.get(node, 0)
            if state == 1:
                return False
            if state == 2:
                return True
            color[node] = 1
            for target in adjacency.get(node, ()):
                if not visit(target):
                    return False
            color[node] = 2
            return True

        nodes = set(adjacency)
        nodes.update(relation.target_id for relation in self._edges.values())
        return all(visit(node) for node in nodes)

    def reachable(self, start_id: str) -> frozenset[str]:
        adjacency: dict[str, list[str]] = {}
        for relation in self._edges.values():
            adjacency.setdefault(relation.source_id, []).append(relation.target_id)

        if start_id not in adjacency:
            return frozenset()

        visited = {start_id}
        stack = [start_id]
        while stack:
            node = stack.pop()
            for target in adjacency.get(node, ()):
                if target not in visited:
                    visited.add(target)
                    stack.append(target)
        visited.discard(start_id)
        return frozenset(visited)


@dataclass(frozen=True)
class Sample:
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


def _snapshot_diff(
    before: tracemalloc.Snapshot, after: tracemalloc.Snapshot
) -> tuple[dict[str, int | str], ...]:
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


def _measure(operation) -> Sample:
    gc.collect()
    tracemalloc.start()
    tracemalloc.reset_peak()
    rss_before = _rss_bytes()
    before = tracemalloc.take_snapshot()
    started = perf_counter_ns()
    operation()
    elapsed_ns = perf_counter_ns() - started
    after = tracemalloc.take_snapshot()
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    rss_after = _rss_bytes()
    diff = _snapshot_diff(before, after)
    tracemalloc.stop()
    return Sample(
        elapsed_ns=elapsed_ns,
        current_bytes=current_bytes,
        peak_bytes=peak_bytes,
        rss_before_bytes=rss_before,
        rss_after_bytes=rss_after,
        snapshot_diff=diff,
    )


def _phase(samples: list[Sample]) -> dict:
    return {
        "samples": [
            {
                "elapsed_ns": sample.elapsed_ns,
                "current_bytes": sample.current_bytes,
                "peak_bytes": sample.peak_bytes,
                "rss_before_bytes": sample.rss_before_bytes,
                "rss_after_bytes": sample.rss_after_bytes,
                "rss_delta_bytes": sample.rss_delta_bytes,
                "snapshot_diff": list(sample.snapshot_diff),
            }
            for sample in samples
        ],
        "median_elapsed_ns": int(statistics.median(s.elapsed_ns for s in samples)),
        "median_current_bytes": int(statistics.median(s.current_bytes for s in samples)),
        "median_peak_bytes": int(statistics.median(s.peak_bytes for s in samples)),
        "median_rss_delta_bytes": int(statistics.median(s.rss_delta_bytes for s in samples)),
    }


def _baseline_view(graph: ObservationAdjacencyGraph) -> ObservationAdjacencyGraph:
    return graph.subgraph_view(TARGET_RELATION)


def _candidate_view(graph: ObservationAdjacencyGraph) -> ViewBuilder:
    return ViewBuilder(graph, TARGET_RELATION)


def _edge_keys(view) -> frozenset[str]:
    return frozenset(view._edges)


def collect_profile(profile: str) -> dict:
    relations = build_relations(profile)
    graph = ObservationAdjacencyGraph(relations)
    baseline = _baseline_view(graph)
    candidate = _candidate_view(graph)

    base_relation_by_hash = {relation.edge_hash: relation for relation in relations}
    alias_count = sum(
        candidate._edges[edge_hash] is base_relation_by_hash[edge_hash]
        for edge_hash in candidate._edges
    )

    assert _edge_keys(candidate) == _edge_keys(baseline)
    assert candidate.is_acyclic() == baseline.is_acyclic()

    reachable_nodes = [relation.source_id for relation in relations[:5]]
    for start_id in reachable_nodes:
        assert candidate.reachable(start_id) == baseline.reachable(start_id)

    def baseline_build() -> ObservationAdjacencyGraph:
        return _baseline_view(graph)

    def candidate_build() -> ViewBuilder:
        return _candidate_view(graph)

    _warmup(baseline_build)
    _warmup(candidate_build)

    baseline_samples = [_measure(baseline_build) for _ in range(SAMPLES)]
    candidate_samples = [_measure(candidate_build) for _ in range(SAMPLES)]

    baseline_view = baseline_build()
    candidate_view = candidate_build()

    return {
        "profile": profile,
        "V": V,
        "E": E,
        "seed": SEED,
        "target_relation": TARGET_RELATION,
        "target_edge_count": len(baseline._edges),
        "alias_parity": {
            "aliased_relation_objects": alias_count,
            "all_view_relations_alias_base": alias_count == len(candidate._edges),
        },
        "semantic_parity": {
            "edge_set_equal": _edge_keys(candidate) == _edge_keys(baseline),
            "is_acyclic_equal": candidate.is_acyclic() == baseline.is_acyclic(),
            "reachable_equal": all(
                candidate.reachable(start_id) == baseline.reachable(start_id)
                for start_id in reachable_nodes
            ),
        },
        "baseline": _phase(baseline_samples),
        "candidate": _phase(candidate_samples),
        "structure": {
            "baseline_node_to_idx_count": len(baseline_view._node_to_idx),
            "baseline_idx_to_node_count": len(baseline_view._idx_to_node),
            "baseline_adj_int_rows": len(baseline_view._adj_int),
            "candidate_has_node_to_idx": hasattr(candidate_view, "_node_to_idx"),
            "candidate_has_idx_to_node": hasattr(candidate_view, "_idx_to_node"),
            "candidate_has_adj_int": hasattr(candidate_view, "_adj_int"),
        },
    }


def _warmup(operation) -> None:
    for _ in range(WARMUP):
        operation()


def build_artifact() -> dict:
    profiles = [collect_profile(profile) for profile in PROFILES]
    return {
        "protocol": "MEM-OPT-v0",
        "status": "MEASURED",
        "candidate": "OPT-1 ViewBuilder",
        "baseline": "ObservationAdjacencyGraph(tuple(filtered_edges.values()))",
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
            "warmup": WARMUP,
            "samples": SAMPLES,
        },
        "invariants": {
            "alias_parity_required": True,
            "semantic_parity_required": True,
            "core_protection": "src/jamp delta = 0",
        },
        "thresholds": None,
        "production_changes": 0,
        "runtime_changes": 0,
    }


def test_opt1_harness_contract() -> None:
    artifact = build_artifact()
    assert artifact["protocol"] == "MEM-OPT-v0"
    assert artifact["thresholds"] is None
    assert artifact["production_changes"] == 0
    assert artifact["runtime_changes"] == 0
    assert [item["profile"] for item in artifact["profiles"]] == list(PROFILES)
    assert all(
        item["alias_parity"]["all_view_relations_alias_base"]
        for item in artifact["profiles"]
    )
    assert all(
        all(item["semantic_parity"].values())
        for item in artifact["profiles"]
    )


def test_opt1_artifact_is_serializable(tmp_path: Path) -> None:
    artifact = build_artifact()
    output = tmp_path / "benchmark-memory-opt.json"
    output.write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["protocol"] == "MEM-OPT-v0"
