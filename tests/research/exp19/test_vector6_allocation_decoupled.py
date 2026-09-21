"""EXP-19 Vector #6: decoupled timing/allocation probe.

Research-only. Phase A measures clean runtime latency; Phase B profiles
allocations separately with tracemalloc. Production JAMP code is untouched.
"""

from __future__ import annotations

import json
import math
import random
import time
import tracemalloc
import warnings

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

N = 40
SEED = 1905
EDGE_COUNT = 10_000
WARMUP = 5


def _graph() -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(EDGE_COUNT // 2)
    ]
    edges.extend(
        ObservationRelation(
            str(i), str(i + EDGE_COUNT // 2), "adjacent", {}
        )
        for i in range(EDGE_COUNT // 2)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _dispatch() -> list[int]:
    values = list(range(N))
    random.Random(SEED).shuffle(values)
    return values


def _phase_a() -> list[float]:
    graph = _graph()
    latencies: list[float] = []
    for position, _iteration_id in enumerate(_dispatch()):
        start = time.perf_counter()
        assert graph.is_acyclic() is True
        graph.reachable("0")
        elapsed_ms = (time.perf_counter() - start) * 1_000.0
        if position >= WARMUP:
            latencies.append(elapsed_ms)
    return latencies


def _phase_b() -> list[tuple[int, int]]:
    graph = _graph()
    dispatch = _dispatch()
    deltas: list[tuple[int, int]] = []

    tracemalloc.start()
    try:
        for position, _iteration_id in enumerate(dispatch):
            tracemalloc.reset_peak()
            before = tracemalloc.take_snapshot()
            graph.is_acyclic()
            graph.reachable("0")
            after = tracemalloc.take_snapshot()
            if position >= WARMUP:
                stats = after.compare_to(before, "lineno")
                allocated_bytes = sum(
                    max(stat.size_diff, 0) for stat in stats
                )
                allocated_blocks = sum(
                    max(stat.count_diff, 0) for stat in stats
                )
                deltas.append((allocated_bytes, allocated_blocks))
    finally:
        tracemalloc.stop()
    return deltas


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("correlation requires equal-length samples")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    centered_x = [x - mean_x for x in xs]
    centered_y = [y - mean_y for y in ys]
    denominator = math.sqrt(
        sum(value * value for value in centered_x)
        * sum(value * value for value in centered_y)
    )
    if denominator == 0.0:
        raise ValueError("correlation is undefined for a constant sequence")
    return sum(
        x * y for x, y in zip(centered_x, centered_y, strict=True)
    ) / denominator


def test_vector6_decoupled_allocation_probe() -> None:
    phase_a = _phase_a()
    phase_b = _phase_b()

    assert len(phase_a) == N - WARMUP
    assert len(phase_b) == N - WARMUP
    assert all(math.isfinite(value) and value >= 0.0 for value in phase_a)
    assert all(bytes_ >= 0 and blocks >= 0 for bytes_, blocks in phase_b)

    bytes_corr = _pearson(
        phase_a, [bytes_ for bytes_, _blocks in phase_b]
    )
    blocks_corr = _pearson(
        phase_a, [blocks for _bytes, blocks in phase_b]
    )

    payload = {
        "edge_count": EDGE_COUNT,
        "iteration_count": N,
        "warmup_excluded": WARMUP,
        "seed": SEED,
        "phase_a_samples": len(phase_a),
        "phase_b_samples": len(phase_b),
        "allocation_bytes_correlation": bytes_corr,
        "allocation_blocks_correlation": blocks_corr,
    }
    warnings.warn(
        "EXP19_VECTOR6_ALLOCATION: "
        + json.dumps(payload, separators=(",", ":"), sort_keys=True),
        UserWarning,
        stacklevel=2,
    )
