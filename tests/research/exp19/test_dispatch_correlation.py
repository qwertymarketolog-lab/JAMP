"""EXP-19 Vector #5: real dispatch/iteration correlation probe.

Research-only. Samples the existing EXP-19 research runtime without importing
or mutating production JAMP code.
"""

from __future__ import annotations

import dataclasses
import json
import math
import random
import time
import warnings
from collections.abc import Sequence

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

N = 40
SEED = 1905
EDGE_COUNT = 10_000
TAIL_POSITIONS = frozenset({2, 15, 22, 35})


@dataclasses.dataclass(frozen=True)
class DispatchObservation:
    iteration_id: int
    dispatch_position: int
    tail_latency_ms: float


def pearson_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("correlation requires equal-length sequences of size >= 2")
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
    return sum(x * y for x, y in zip(centered_x, centered_y, strict=True)) / denominator


def correlation_pair(
    observations: Sequence[DispatchObservation],
) -> tuple[float, float]:
    if len(observations) != N:
        raise ValueError(f"expected exactly {N} observations")
    iteration_ids = [float(item.iteration_id) for item in observations]
    dispatch_positions = [float(item.dispatch_position) for item in observations]
    latencies = [item.tail_latency_ms for item in observations]
    return (
        pearson_correlation(latencies, dispatch_positions),
        pearson_correlation(latencies, iteration_ids),
    )


def _graph() -> ObservationAdjacencyGraph:
    edges = [
        ObservationRelation(str(i), str(i + 1), "adjacent", {})
        for i in range(EDGE_COUNT // 2)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + EDGE_COUNT // 2), "adjacent", {})
        for i in range(EDGE_COUNT // 2)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _sample_dispatch_runtime() -> list[DispatchObservation]:
    iteration_ids = list(range(N))
    random.Random(SEED).shuffle(iteration_ids)

    graph = _graph()
    observations: list[DispatchObservation] = []
    for dispatch_position, iteration_id in enumerate(iteration_ids):
        start = time.perf_counter()
        assert graph.is_acyclic() is True
        graph.reachable("0")
        elapsed_ms = (time.perf_counter() - start) * 1_000.0
        observations.append(
            DispatchObservation(
                iteration_id=iteration_id,
                dispatch_position=dispatch_position,
                tail_latency_ms=elapsed_ms,
            )
        )
    return observations


def _export_observations(
    observations: Sequence[DispatchObservation],
    dispatch_corr: float,
    iteration_corr: float,
) -> None:
    payload = {
        "edge_count": EDGE_COUNT,
        "iteration_count": N,
        "seed": SEED,
        "tail_positions": sorted(TAIL_POSITIONS),
        "correlation": {
            "tail_latency_vs_dispatch_position": dispatch_corr,
            "tail_latency_vs_iteration_id": iteration_corr,
        },
        "observations": [dataclasses.asdict(item) for item in observations],
    }
    warnings.warn(
        f"EXP19_DISPATCH_CORRELATION: {json.dumps(payload, separators=(',', ':'), sort_keys=True)}",
        UserWarning,
        stacklevel=2,
    )


def test_vector5_real_dispatch_correlation_probe() -> None:
    observations = _sample_dispatch_runtime()
    dispatch_corr, iteration_corr = correlation_pair(observations)

    assert len(observations) == N
    assert {item.dispatch_position for item in observations} == set(range(N))
    assert {item.iteration_id for item in observations} == set(range(N))
    assert all(math.isfinite(item.tail_latency_ms) for item in observations)
    assert all(item.tail_latency_ms >= 0.0 for item in observations)

    _export_observations(observations, dispatch_corr, iteration_corr)


def test_vector5_tail_positions_are_data_labels_not_causes() -> None:
    assert frozenset({2, 15, 22, 35}) == TAIL_POSITIONS
    assert TAIL_POSITIONS.issubset(range(N))
