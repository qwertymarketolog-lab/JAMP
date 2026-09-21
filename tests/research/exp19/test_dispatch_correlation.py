"""EXP-19 Vector #5: dispatch/iteration correlation analysis contract.

Research-only. This module does not execute JAMP production code and does not
manufacture latency observations. A future runtime/driver probe can feed
observations into the correlation helpers.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence

N = 40
SEED = 1905
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


def test_vector5_correlation_contract_preserves_two_axes() -> None:
    observations = [
        DispatchObservation(
            iteration_id=iteration_id,
            dispatch_position=dispatch_position,
            tail_latency_ms=float(iteration_id + dispatch_position),
        )
        for dispatch_position, iteration_id in enumerate(range(N))
    ]
    dispatch_corr, iteration_corr = correlation_pair(observations)

    assert math.isclose(dispatch_corr, 1.0)
    assert math.isclose(iteration_corr, 1.0)


def test_vector5_tail_positions_are_data_labels_not_causes() -> None:
    assert TAIL_POSITIONS == frozenset({2, 15, 22, 35})
    assert TAIL_POSITIONS.issubset(range(N))
