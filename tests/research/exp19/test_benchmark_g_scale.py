from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import pytest

from tests.research.exp19.conftest_bench import PROFILES, build_graph
from research.exp19.adjacency_graph import ObservationAdjacencyGraph


pytestmark = pytest.mark.skipif(
    os.getenv("JAMP_R3_BENCHMARK") != "1",
    reason="EXP-19.R3 benchmark runs only in the dedicated benchmark job",
)

SAMPLES = 10
TARGET_TYPE = "CTRL"


def compute_stats(samples: list[int]) -> dict[str, float | int]:
    sorted_samples = sorted(samples)
    n = len(sorted_samples)
    p95_index = int(0.95 * (n - 1))
    return {
        "min_ns": sorted_samples[0],
        "max_ns": sorted_samples[-1],
        "median_ns": statistics.median(samples),
        "mean_ns": statistics.mean(samples),
        "p95_ns": sorted_samples[p95_index],
    }


def _measure(operation, samples: int = SAMPLES) -> list[int]:
    timings: list[int] = []
    for _ in range(samples):
        start = time.perf_counter_ns()
        operation()
        timings.append(time.perf_counter_ns() - start)
    return timings


def _representative_node(view: ObservationAdjacencyGraph) -> str:
    nodes = getattr(view, "_node_to_idx", {})
    if nodes:
        return next(iter(nodes))
    return "n00000"


def test_g_scale_benchmark(tmp_path: Path) -> None:
    measurements: list[dict[str, object]] = []

    for profile in PROFILES:
        graph = build_graph(profile=profile, seed=42, v=10_000, e=20_000)

        # One warm-up per operation/profile; no latency threshold is asserted.
        warm_view = graph.subgraph_view(TARGET_TYPE)
        _ = warm_view.is_acyclic()
        _ = warm_view.reachable(_representative_node(warm_view))

        view_samples = _measure(
            lambda graph=graph: graph.subgraph_view(TARGET_TYPE)
        )
        active_view = graph.subgraph_view(TARGET_TYPE)
        acyclic_samples = _measure(active_view.is_acyclic)
        sample_node = _representative_node(active_view)
        reachable_samples = _measure(
            lambda active_view=active_view, sample_node=sample_node: active_view.reachable(
                sample_node
            )
        )

        for operation, samples in (
            ("subgraph_view", view_samples),
            ("is_acyclic", acyclic_samples),
            ("reachable", reachable_samples),
        ):
            measurements.append(
                {
                    "profile": profile,
                    "relation_type": TARGET_TYPE,
                    "operation": operation,
                    "samples_ns": samples,
                    **compute_stats(samples),
                }
            )

    report = {
        "experiment": "EXP-19.R3",
        "protocol_version": "R3-v0",
        "seed": 42,
        "vertices": 10_000,
        "edges": 20_000,
        "samples_per_operation": SAMPLES,
        "profiles": list(PROFILES),
        "operations": ["subgraph_view", "is_acyclic", "reachable"],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "runner": os.getenv("GITHUB_RUN_ID", "local"),
        },
        "measurements": measurements,
    }

    out_dir = Path("artifacts/exp19-r3")
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "benchmark.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    tmp_output = tmp_path / "benchmark.json"
    tmp_output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert output.exists()
    assert tmp_output.exists()
    assert len(measurements) == len(PROFILES) * 3
    assert all(len(item["samples_ns"]) == SAMPLES for item in measurements)
