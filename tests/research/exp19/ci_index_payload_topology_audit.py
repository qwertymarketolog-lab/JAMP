"""EXP-19 Vector #4: audit index-to-payload topology mapping, read-only."""

from __future__ import annotations

import contextlib
from collections import Counter
from unittest.mock import patch

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from tests.research.exp19.test_adjacency_graph import (
    test_g4_large_graph_is_linear_scale as canonical_g4,
)

N = 40


def _fingerprint(graph: ObservationAdjacencyGraph) -> tuple[int, int, tuple[int, ...]]:
    edges = graph._edges.values()  # noqa: SLF001
    out_degrees = tuple(sorted(len(targets) for targets in graph._adj_int))  # noqa: SLF001
    return len(graph._idx_to_node), len(graph._edges), out_degrees  # noqa: SLF001


def test_vector4_index_payload_topology_audit() -> None:
    fingerprints: list[tuple[int, int, tuple[int, ...]]] = []
    captured_indices: list[int] = []
    original_acyclic = ObservationAdjacencyGraph.is_acyclic

    for index in range(1, N + 1):
        graph_ref: dict[str, ObservationAdjacencyGraph] = {}

        def capture(
            self: ObservationAdjacencyGraph,
            graph_ref: dict[str, ObservationAdjacencyGraph] = graph_ref,
        ) -> bool:
            graph_ref["graph"] = self
            return original_acyclic(self)

        with (
            patch.object(ObservationAdjacencyGraph, "is_acyclic", capture),
            contextlib.suppress(AssertionError),
        ):
            canonical_g4()

        graph = graph_ref["graph"]
        fingerprints.append(_fingerprint(graph))
        captured_indices.append(index)

    unique = set(fingerprints)
    print("EXP-19 VECTOR #4 — INDEX-PAYLOAD TOPOLOGY AUDIT — READ ONLY")
    print(f"iterations={captured_indices}")
    print(f"unique_topology_count={len(unique)}")
    print(f"topology_frequency={Counter(fingerprints)}")
    print(f"topology_fingerprint={fingerprints[0]}")
    assert len(unique) == 1
