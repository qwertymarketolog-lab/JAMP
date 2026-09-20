"""EXP-19: execute the canonical G4 test function repeatedly, read-only."""
from __future__ import annotations

import statistics
import time
from unittest.mock import patch

from tests.research.exp19.test_adjacency_graph import test_g4_large_graph_is_linear_scale

REAL_PERF_COUNTER = time.perf_counter


def run_once() -> float:
    calls: list[float] = []

    def traced_perf_counter() -> float:
        value = REAL_PERF_COUNTER()
        calls.append(value)
        return value

    with patch("time.perf_counter", side_effect=traced_perf_counter):
        try:
            test_g4_large_graph_is_linear_scale()
        except AssertionError:
            pass

    assert len(calls) == 2, calls
    return (calls[1] - calls[0]) * 1000.0


def test_exp19_official_hard_guard_multisample() -> None:
    samples = [run_once() for _ in range(10)]
    ordered = sorted(samples)
    p50 = statistics.median(ordered)
    p95 = ordered[-1]
    p99 = ordered[-1]
    maximum = ordered[-1]

    print("EXP-19 OFFICIAL HARD-GUARD MULTI-SAMPLE — READ ONLY")
    print(f"samples_ms={[round(x, 3) for x in samples]}")
    print(
        f"p50_ms={p50:.3f} p95_ms={p95:.3f} "
        f"p99_ms={p99:.3f} max_ms={maximum:.3f}"
    )
    print("contract_ms=15.000")
    print("historical_fail_ms=23.068216")
