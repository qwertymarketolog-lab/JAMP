"""EXP-19 Vector #5-B: multi-seed dispatch/iteration correlation probe.

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
SEEDS = (1905, 2026, 42, 100, 7, 314, 271, 512, 1024, 8888)
EDGE_COUNT = 10_000
TAIL_POSITIONS = frozenset({2, 15, 22, 35})
T_CRITICAL_95_K10 = 2.262157


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
        sum(value * value for value in centered_x) * sum(value * value for value in centered_y)
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
        ObservationRelation(str(i), str(i + 1), "adjacent", {}) for i in range(EDGE_COUNT // 2)
    ]
    edges.extend(
        ObservationRelation(str(i), str(i + EDGE_COUNT // 2), "adjacent", {})
        for i in range(EDGE_COUNT // 2)
    )
    return ObservationAdjacencyGraph(tuple(edges))


def _sample_dispatch_runtime(seed: int) -> list[DispatchObservation]:
    iteration_ids = list(range(N))
    random.Random(seed).shuffle(iteration_ids)

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


def _mean_and_ci(values: Sequence[float]) -> tuple[float, float, float]:
    if not values:
        raise ValueError("cannot aggregate an empty sample")
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, mean, mean
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    standard_error = math.sqrt(variance / len(values))
    margin = T_CRITICAL_95_K10 * standard_error
    return mean, mean - margin, mean + margin


def _aggregate(
    correlations: Sequence[tuple[float, float]],
) -> dict[str, dict[str, float]]:
    dispatch = [pair[0] for pair in correlations]
    iteration = [pair[1] for pair in correlations]
    dispatch_mean, dispatch_low, dispatch_high = _mean_and_ci(dispatch)
    iteration_mean, iteration_low, iteration_high = _mean_and_ci(iteration)
    return {
        "tail_latency_vs_dispatch_position": {
            "mean": dispatch_mean,
            "ci95_low": dispatch_low,
            "ci95_high": dispatch_high,
        },
        "tail_latency_vs_iteration_id": {
            "mean": iteration_mean,
            "ci95_low": iteration_low,
            "ci95_high": iteration_high,
        },
    }


def _export_sweep(
    seed_results: Sequence[dict[str, object]],
    aggregate: dict[str, dict[str, float]],
) -> None:
    payload = {
        "edge_count": EDGE_COUNT,
        "iteration_count": N,
        "seed_count": len(SEEDS),
        "seeds": list(SEEDS),
        "tail_positions": sorted(TAIL_POSITIONS),
        "aggregate": aggregate,
        "per_seed": seed_results,
    }
    warnings.warn(
        f"EXP19_DISPATCH_CORRELATION_SWEEP: "
        f"{json.dumps(payload, separators=(',', ':'), sort_keys=True)}",
        UserWarning,
        stacklevel=2,
    )


def test_vector5b_multi_seed_dispatch_correlation_probe() -> None:
    seed_results: list[dict[str, object]] = []
    correlations: list[tuple[float, float]] = []

    for seed in SEEDS:
        observations = _sample_dispatch_runtime(seed)
        dispatch_corr, iteration_corr = correlation_pair(observations)
        correlations.append((dispatch_corr, iteration_corr))
        seed_results.append(
            {
                "seed": seed,
                "dispatch_correlation": dispatch_corr,
                "iteration_correlation": iteration_corr,
                "observation_count": len(observations),
            }
        )

        assert {item.dispatch_position for item in observations} == set(range(N))
        assert {item.iteration_id for item in observations} == set(range(N))
        assert all(math.isfinite(item.tail_latency_ms) for item in observations)
        assert all(item.tail_latency_ms >= 0.0 for item in observations)

    aggregate = _aggregate(correlations)
    assert len(seed_results) == len(SEEDS)
    assert all(
        math.isfinite(value)
        for result in aggregate.values()
        for value in result.values()
    )

    _export_sweep(seed_results, aggregate)


def test_vector5_tail_positions_are_data_labels_not_causes() -> None:
    assert frozenset({2, 15, 22, 35}) == TAIL_POSITIONS
    assert TAIL_POSITIONS.issubset(range(N))
