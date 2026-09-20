"""Read-only EXP-19 forensic performance boundary benchmark.

This benchmark does not modify production/runtime code. It times the existing
ObservationAdjacencyGraph representation and isolated traversal phases on CI.
"""

from __future__ import annotations

import statistics
import time

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


EDGES = [(str(i), str(i + 1)) for i in range(10_000)]
EDGES.extend((str(i), str(i + 10_000)) for i in range(10_000))
REPEATS = 5


def build_graph() -> ObservationAdjacencyGraph:
    return ObservationAdjacencyGraph(
        tuple(ObservationRelation(s, t, "adjacent", {}) for s, t in EDGES)
    )


def timed(fn, repeats: int = REPEATS) -> list[float]:
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


def current_acyclic(g: ObservationAdjacencyGraph) -> bool:
    return g.is_acyclic()


def bfs_no_materialization(g: ObservationAdjacencyGraph) -> int:
    from collections import deque

    start_idx = g._node_to_idx["0"]
    visited = {start_idx}
    queue = deque([start_idx])
    popleft = queue.popleft
    visited_add = visited.add
    queue_append = queue.append
    adj = g._adj_int

    while queue:
        node = popleft()
        for target in adj[node]:
            if target not in visited:
                visited_add(target)
                queue_append(target)

    visited.discard(start_idx)
    return len(visited)


def bfs_with_materialization(g: ObservationAdjacencyGraph) -> frozenset[str]:
    from collections import deque

    start_idx = g._node_to_idx["0"]
    visited = {start_idx}
    queue = deque([start_idx])
    popleft = queue.popleft
    visited_add = visited.add
    queue_append = queue.append
    adj = g._adj_int

    while queue:
        node = popleft()
        for target in adj[node]:
            if target not in visited:
                visited_add(target)
                queue_append(target)

    visited.discard(start_idx)
    idx_to_node = g._idx_to_node
    return frozenset(idx_to_node[index] for index in visited)


def materialize_from_visited(g: ObservationAdjacencyGraph) -> frozenset[str]:
    from collections import deque

    start_idx = g._node_to_idx["0"]
    visited = {start_idx}
    queue = deque([start_idx])
    popleft = queue.popleft
    visited_add = visited.add
    queue_append = queue.append
    adj = g._adj_int

    while queue:
        node = popleft()
        for target in adj[node]:
            if target not in visited:
                visited_add(target)
                queue_append(target)

    visited.discard(start_idx)
    idx_to_node = g._idx_to_node
    start = time.perf_counter()
    result = frozenset(idx_to_node[index] for index in visited)
    elapsed = time.perf_counter() - start
    if len(result) != 19_999:
        raise AssertionError(f"unexpected result size: {len(result)}")
    return elapsed


def summarize(name: str, samples: list[float]) -> None:
    print(
        f"{name}: "
        f"median={statistics.median(samples) * 1000:.3f} ms "
        f"min={min(samples) * 1000:.3f} ms "
        f"max={max(samples) * 1000:.3f} ms "
        f"samples={[round(x * 1000, 3) for x in samples]}"
    )


def main() -> None:
    g = build_graph()

    if not g.is_acyclic():
        raise AssertionError("benchmark graph must be acyclic")
    if len(g.reachable("0")) != 19_999:
        raise AssertionError("unexpected baseline reachability size")

    # Warm-up before the measured repetitions.
    current_acyclic(g)
    bfs_no_materialization(g)
    bfs_with_materialization(g)
    materialize_from_visited(g)

    acyclic = timed(lambda: current_acyclic(g))
    bfs = timed(lambda: bfs_no_materialization(g))
    full_reachable = timed(lambda: bfs_with_materialization(g))
    materialization = timed(lambda: materialize_from_visited(g))

    print("EXP-19 FORENSIC BOUNDARY — READ ONLY")
    print(f"payload: vertices={g._v_count} edges={len(EDGES)} repeats={REPEATS}")
    summarize("is_acyclic", acyclic)
    summarize("reachable_traversal_only", bfs)
    summarize("reachable_full_current", full_reachable)
    summarize("materialization_only", materialization)
    print("contract_ms=15.000")
    print(
        "decision_signal: "
        f"acyclic_median_ms={statistics.median(acyclic) * 1000:.3f}, "
        f"bfs_median_ms={statistics.median(bfs) * 1000:.3f}"
    )


if __name__ == "__main__":
    main()
