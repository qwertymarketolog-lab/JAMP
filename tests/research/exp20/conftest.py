"""Non-intrusive environment attribution telemetry for EXP-20."""

from __future__ import annotations

import gc
import json
import os
import platform
import sys
import time

_G4_NODEID = "tests/research/exp19/test_adjacency_graph.py::test_g4_large_graph_is_linear_scale"


def _context() -> dict[str, object]:
    return {
        "python": sys.version,
        "python_implementation": platform.python_implementation(),
        "os": platform.platform(),
        "runner_image": os.environ.get("ImageOS"),
        "runner_name": os.environ.get("RUNNER_NAME"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "sha": os.environ.get("GITHUB_SHA"),
        "nodeid": _G4_NODEID,
        "gc_enabled": gc.isenabled(),
        "gc_count": gc.get_count(),
        "gc_threshold": gc.get_threshold(),
        "gc_stats": gc.get_stats(),
    }


def _emit(phase: str, elapsed_ms: float | None = None) -> None:
    record = {"phase": phase, "elapsed_ms": elapsed_ms, **_context()}
    print(f"EXP20_ENV_TELEMETRY {json.dumps(record, sort_keys=True)}", flush=True)


def pytest_runtest_setup(item) -> None:
    if item.nodeid == _G4_NODEID:
        _emit("before")


def pytest_runtest_call(item):
    if item.nodeid == _G4_NODEID:
        started = time.perf_counter()
        yield
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _emit("after", elapsed_ms)
    else:
        yield


pytest_runtest_call.hookwrapper = True


def pytest_runtest_teardown(item, nextitem) -> None:
    if item.nodeid == _G4_NODEID:
        _emit("teardown")


def pytest_sessionstart(session) -> None:
    print(
        "EXP20_ENV_SESSION "
        + json.dumps(
            {
                "run_id": os.environ.get("GITHUB_RUN_ID"),
                "sha": os.environ.get("GITHUB_SHA"),
                "python": sys.version,
                "os": platform.platform(),
            },
            sort_keys=True,
        ),
        flush=True,
    )
