"""Controlled GC intervention for EXP-19 G4 attribution.

This research-only hook performs one explicit gc.collect() immediately before
the existing G4 test body. The G4 body, timer, threshold, and production
runtime remain unchanged.
"""

from __future__ import annotations

import gc
import resource

_G4_NODEID = "tests/research/exp19/test_adjacency_graph.py::test_g4_large_graph_is_linear_scale"


def _emit(phase: str) -> None:
    stats = gc.get_stats()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(
        "EXP19_G4_MACRO_TELEMETRY "
        f"phase={phase} "
        f"gc_enabled={gc.isenabled()} "
        f"gc_count={gc.get_count()} "
        f"gc_threshold={gc.get_threshold()} "
        f"gc_stats={stats!r} "
        f"ru_maxrss={rss}",
        flush=True,
    )


def pytest_runtest_setup(item) -> None:
    if item.nodeid.endswith(_G4_NODEID):
        gc.collect()
        _emit("before")


def pytest_runtest_teardown(item, nextitem) -> None:
    if item.nodeid.endswith(_G4_NODEID):
        _emit("after")
