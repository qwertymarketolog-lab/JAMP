"""EXP-19.MEM — deterministic memory benchmark harness.

Measurement only: no memory budget or pass/fail threshold is asserted.
"""

from __future__ import annotations

import gc
import json
import os
import random
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

import psutil

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


PROFILES = (
    "single",
    "mixed",
    "rare",
    "dominant",
    "empty",
    "near-complete",
)

V = 10_000
E = 20_000
SEED = 42
WARMUP = 1
SAMPLES = 10
TARGET_RELATION = "DEP"

ARTIFACT_PATH = Path("artifacts/exp19-mem/benchmark-memory.json")


@dataclass(frozen=True)
class MemorySample:
    elapsed_ns: int
    current_bytes: int
    peak_bytes: int
    rss_before_bytes: int
    rss_after_bytes: int

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


def measure_once(operation) -> MemorySample:
    gc.collect()
    tracemalloc.start()
    before_rss = _rss_bytes()
    started = perf_counter_ns()

    operation()

    elapsed_ns = perf_counter_ns() - started
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    after_rss = _rss_bytes()
    tracemalloc.stop()

    return MemorySample(
        elapsed_ns=elapsed_ns,
        current_bytes=current_bytes,
        peak_bytes=peak_bytes,
        rss_before_bytes=before_rss,
        rss_after_bytes=after_rss,
    )


def collect_profile(profile: str) -> dict:
    graph, relations = build_graph(profile)

    # The identity check is performed against the immutable relation objects
    # passed into the base graph; subgraph_view must not clone payload objects.
    view = graph.subgraph_view(TARGET_RELATION)
    base_relation_by_hash = {relation.edge_hash: relation for relation in relations}
    alias_count = sum(
        view_relation is base_relation_by_hash[edge_hash]
        for edge_hash, view_relation in view._edges.items()
    )

    samples: list[MemorySample] = []

    def operation() -> None:
        graph.subgraph_view(TARGET_RELATION)

    for _ in range(WARMUP):
        operation()

    for _ in range(SAMPLES):
        samples.append(measure_once(operation))

    return {
        "profile": profile,
        "V": V,
        "E": E,
        "seed": SEED,
        "target_relation": TARGET_RELATION,
        "warmup": WARMUP,
        "samples": [
            {
                "elapsed_ns": sample.elapsed_ns,
                "current_bytes": sample.current_bytes,
                "peak_bytes": sample.peak_bytes,
                "rss_before_bytes": sample.rss_before_bytes,
                "rss_after_bytes": sample.rss_after_bytes,
                "rss_delta_bytes": sample.rss_delta_bytes,
            }
            for sample in samples
        ],
        "aliasing": {
            "view_edge_count": len(view._edges),
            "aliased_relation_objects": alias_count,
            "all_view_relations_alias_base": alias_count == len(view._edges),
        },
    }


def build_artifact() -> dict:
    return {
        "protocol": "MEM-v0",
        "profiles": [collect_profile(profile) for profile in PROFILES],
        "measurement": {
            "tracemalloc": "current_and_peak_bytes",
            "rss": "process_rss_before_after_and_delta_bytes",
            "timing": "perf_counter_ns",
            "aliasing": "object_identity_against_base_relations",
        },
        "thresholds": None,
        "status": "MEASURED",
    }


def test_memory_benchmark_harness_schema_and_aliasing() -> None:
    artifact = build_artifact()

    assert artifact["protocol"] == "MEM-v0"
    assert [item["profile"] for item in artifact["profiles"]] == list(PROFILES)
    assert artifact["thresholds"] is None
    assert all(
        item["aliasing"]["all_view_relations_alias_base"]
        for item in artifact["profiles"]
    )


def test_memory_benchmark_artifact_is_serializable(tmp_path: Path) -> None:
    artifact = build_artifact()
    output = tmp_path / "benchmark-memory.json"
    output.write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["protocol"] == "MEM-v0"
