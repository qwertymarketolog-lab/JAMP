"""Research-only G4 telemetry probe; does not modify the locked G4 gate."""

from __future__ import annotations

import gc
import json
import time
import warnings

import pytest

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


def _graph() -> ObservationAdjacencyGraph:
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {}) for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


@pytest.mark.exp20_telemetry
def test_g4_wall_vs_process_cpu_and_gc_telemetry() -> None:
    gc_events: list[tuple[str, int, float]] = []
    started: dict[tuple[str, int], float] = {}

    def gc_callback(phase: str, info: dict[str, object]) -> None:
        generation = int(info.get("generation", -1))
        key = (phase, generation)
        now = time.perf_counter()
        if phase == "start":
            started[key] = now
        elif phase == "stop":
            start = started.pop(("start", generation), None)
            if start is not None:
                gc_events.append(("gc_pause", generation, now - start))

    before_count = tuple(gc.get_count())
    before_stats = tuple(
        {"collections": item["collections"], "collected": item["collected"]}
        for item in gc.get_stats()
    )
    gc.callbacks.append(gc_callback)
    try:
        g = _graph()
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        assert g.is_acyclic() is True
        g.reachable("0")
        cpu_elapsed = time.process_time() - cpu_start
        wall_elapsed = time.perf_counter() - wall_start
    finally:
        gc.callbacks.remove(gc_callback)

    after_count = tuple(gc.get_count())
    after_stats = tuple(
        {"collections": item["collections"], "collected": item["collected"]}
        for item in gc.get_stats()
    )
    payload = {
        "wall_ms": wall_elapsed * 1000.0,
        "process_cpu_ms": cpu_elapsed * 1000.0,
        "non_cpu_elapsed_ms": max(0.0, (wall_elapsed - cpu_elapsed) * 1000.0),
        "gc_count_before": before_count,
        "gc_count_after": after_count,
        "gc_stats_before": before_stats,
        "gc_stats_after": after_stats,
        "gc_events": [
            {"kind": kind, "generation": generation, "pause_ms": pause * 1000.0}
            for kind, generation, pause in gc_events
        ],
    }
    warnings.warn(
        "EXP20_G4_TELEMETRY: " + json.dumps(payload, sort_keys=True),
        UserWarning,
        stacklevel=1,
    )
