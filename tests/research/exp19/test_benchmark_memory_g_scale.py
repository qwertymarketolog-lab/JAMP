"""EXP-19.MEM — memory benchmark harness scaffold.

RED-stage measurement only. No memory budget or pass/fail threshold is asserted.
"""

from __future__ import annotations

import gc
import json
import os
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

import psutil


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

ARTIFACT_PATH = Path("artifacts/exp19-mem/benchmark-memory.json")


@dataclass(frozen=True)
class MemorySample:
    elapsed_ns: int
    current_bytes: int
    peak_bytes: int
    rss_bytes: int


def _rss_bytes() -> int:
    return psutil.Process(os.getpid()).memory_info().rss


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
        rss_bytes=after_rss - before_rss,
    )


def collect_profile(profile: str) -> dict:
    """Placeholder for deterministic graph/view construction.

    The concrete ObservationAdjacencyGraph wiring is intentionally left for the
    RED-stage implementation step; this scaffold fixes measurement semantics
    without introducing a production dependency or a memory threshold.
    """

    samples: list[MemorySample] = []

    def operation() -> None:
        # RED scaffold: replace with the profile-specific view construction.
        return None

    for _ in range(WARMUP):
        operation()

    for _ in range(SAMPLES):
        samples.append(measure_once(operation))

    return {
        "profile": profile,
        "V": V,
        "E": E,
        "seed": SEED,
        "warmup": WARMUP,
        "samples": [sample.__dict__ for sample in samples],
    }


def build_artifact() -> dict:
    return {
        "protocol": "MEM-v0",
        "profiles": [collect_profile(profile) for profile in PROFILES],
        "measurement": {
            "tracemalloc": "current_and_peak_bytes",
            "rss": "process_rss_delta_bytes",
            "timing": "perf_counter_ns",
        },
        "thresholds": None,
        "status": "MEASURED_HARNESS_SCAFFOLD",
    }


def test_memory_benchmark_harness_writes_deterministic_schema(tmp_path: Path) -> None:
    artifact = build_artifact()

    assert artifact["protocol"] == "MEM-v0"
    assert [item["profile"] for item in artifact["profiles"]] == list(PROFILES)
    assert artifact["thresholds"] is None

    output = tmp_path / "benchmark-memory.json"
    output.write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\\n", encoding="utf-8")

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["protocol"] == "MEM-v0"
