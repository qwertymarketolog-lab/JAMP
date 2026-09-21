"""Passive macro-suite telemetry for EXP-19 G4.

This hook observes process state immediately before and after the G4 test
without changing the test body, timer, GC state, or production runtime.
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
        _emit("before")


def pytest_runtest_teardown(item, nextitem) -> None:
    if item.nodeid.endswith(_G4_NODEID):
        _emit("after")
