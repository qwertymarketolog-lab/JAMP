"""Research-only G4 hot-path profiler; never changes the Frozen Core.

Profiles the exact EXP-19 graph operations outside pytest:
ObservationAdjacencyGraph -> is_acyclic() -> reachable("0").
"""

from __future__ import annotations

import cProfile
import json
import os
import platform
import pstats
import subprocess
import sys
import tracemalloc
from pathlib import Path

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation

def resolve_target_commit() -> str:
    """Resolve the profiled commit with fail-closed provenance."""
    env_sha = os.getenv("TARGET_COMMIT", "").strip()
    if env_sha:
        if len(env_sha) == 40 and all(char in "0123456789abcdefABCDEF" for char in env_sha):
            return env_sha
        raise RuntimeError(
            "Path A Provenance Failure: TARGET_COMMIT is not a valid 40-character SHA."
        )

    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception as exc:
        raise RuntimeError(
            "Path A Provenance Failure: Unable to resolve TARGET_COMMIT from "
            "environment or 'git rev-parse HEAD'."
        ) from exc

    if len(git_sha) == 40 and all(char in "0123456789abcdefABCDEF" for char in git_sha):
        return git_sha

    raise RuntimeError(
        "Path A Provenance Failure: 'git rev-parse HEAD' returned an invalid SHA."
    )


OUTPUT = Path("g4_hotpath_profile.json")


def build_graph() -> ObservationAdjacencyGraph:
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    relations = tuple(
        ObservationRelation(source, target, "adjacent", {}) for source, target in edges
    )
    return ObservationAdjacencyGraph(relations)


def target(g: ObservationAdjacencyGraph) -> None:
    if g.is_acyclic() is not True:
        raise AssertionError("fixed G4 graph must be acyclic")
    g.reachable("0")


def main() -> None:
    g = build_graph()

    # Warm up interpreter/runtime without recording warm-up work.
    for _ in range(3):
        target(g)

    profiler = cProfile.Profile()
    tracemalloc.start()
    profiler.enable()
    snapshot_before = tracemalloc.take_snapshot()
    target(g)
    snapshot_after = tracemalloc.take_snapshot()
    profiler.disable()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    stats = pstats.Stats(profiler).sort_stats("tottime")
    total_tottime = float(sum(stat[2] for stat in stats.stats.values()))

    top_functions = []
    for (filename, line, function), (cc, nc, tt, ct, callers) in stats.stats.items():
        if function not in {"is_acyclic", "reachable"}:
            continue
        pct = (tt / total_tottime * 100.0) if total_tottime else 0.0
        top_functions.append(
            {
                "file": str(Path(filename).as_posix()),
                "line": line,
                "function": function,
                "tottime_sec": tt,
                "cumtime_sec": ct,
                "tottime_pct": pct,
                "status": "HOT_PATH_CANDIDATE" if pct > 40.0 else "PROFILED",
            }
        )
    top_functions.sort(key=lambda item: item["tottime_sec"], reverse=True)

    allocations = []
    for stat in snapshot_after.compare_to(snapshot_before, "lineno")[:20]:
        if stat.size_diff <= 0:
            continue
        allocations.append(
            {
                "file": str(stat.traceback[0].filename),
                "line": stat.traceback[0].lineno,
                "size_bytes": stat.size_diff,
                "count": stat.count_diff,
            }
        )

    payload = {
        "target_commit": resolve_target_commit(),
        "profiler_type": "cProfile + tracemalloc",
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "cpu_profile": {
            "total_tottime_sec": total_tottime,
            "top_functions": top_functions,
        },
        "allocation_profile": {
            "peak_memory_bytes": peak_bytes,
            "top_allocations": allocations,
        },
        "epistemic_status": "HOT-PATH CANDIDATE MAP",
        "wall_clock_causality": "NOT_ESTABLISHED",
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
