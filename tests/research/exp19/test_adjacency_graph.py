"""GREEN tests for EXP-19.R1 ObservationAdjacencyGraph."""

from __future__ import annotations

import importlib
import time
import warnings

import pytest

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


def relation(source: str, target: str) -> ObservationRelation:
    return ObservationRelation(source, target, "adjacent", {})


def graph(edges: list[tuple[str, str]]) -> ObservationAdjacencyGraph:
    return ObservationAdjacencyGraph(tuple(relation(s, t) for s, t in edges))


@pytest.mark.parametrize(
    "edges",
    [
        [("A", "B")],
        [("A", "B"), ("B", "C")],
        [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
        [("A", "B"), ("B", "C"), ("C", "D"), ("A", "D")],
        [("A", "B"), ("A", "C"), ("A", "D")],
        [("A", "B"), ("C", "D")],
        [("A", "B"), ("B", "C"), ("B", "D"), ("D", "E")],
        [("A", "B"), ("C", "B"), ("D", "B")],
        [("A", "B"), ("B", "C"), ("C", "E"), ("A", "D"), ("D", "E")],
        [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")],
    ],
)
def test_g1_dag_is_acyclic(edges: list[tuple[str, str]]) -> None:
    assert graph(edges).is_acyclic() is True


@pytest.mark.parametrize(
    "edges",
    [
        [("A", "B"), ("B", "A")],
        [("A", "B"), ("B", "C"), ("C", "A")],
        [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")],
        [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "B")],
        [("A", "B"), ("B", "C"), ("C", "A"), ("C", "D")],
        [("A", "B"), ("C", "D"), ("D", "E"), ("E", "C")],
        [("A", "B"), ("B", "C"), ("C", "D"), ("D", "B"), ("D", "E")],
        [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "A")],
    ],
)
def test_g2_cycle_is_detected(edges: list[tuple[str, str]]) -> None:
    assert graph(edges).is_acyclic() is False


@pytest.mark.parametrize(
    "edges, source, expected",
    [
        ([("A", "B"), ("B", "C"), ("C", "D")], "A", frozenset({"B", "C", "D"})),
        ([("A", "B"), ("B", "C"), ("X", "Y")], "A", frozenset({"B", "C"})),
        (
            [("A", "B"), ("A", "C"), ("B", "D"), ("C", "E")],
            "A",
            frozenset({"B", "C", "D", "E"}),
        ),
        ([("A", "B"), ("B", "C"), ("X", "C")], "X", frozenset({"C"})),
        ([("A", "B"), ("C", "D")], "B", frozenset()),
        (
            [("A", "B"), ("B", "C"), ("C", "D"), ("X", "Y")],
            "C",
            frozenset({"D"}),
        ),
        (
            [("A", "B"), ("A", "C"), ("C", "D"), ("D", "E")],
            "B",
            frozenset(),
        ),
        (
            [("A", "B"), ("B", "D"), ("A", "C"), ("C", "D"), ("D", "E")],
            "A",
            frozenset({"B", "C", "D", "E"}),
        ),
    ],
)
def test_g3_reachability_is_exact(
    edges: list[tuple[str, str]], source: str, expected: frozenset[str]
) -> None:
    assert graph(edges).reachable(source) == expected


def test_g3_unknown_source_is_empty() -> None:
    assert graph([("A", "B")]).reachable("Z") == frozenset()


def test_g3_does_not_include_source() -> None:
    assert "A" not in graph([("A", "B"), ("B", "C")]).reachable("A")


def test_g3_disconnected_component_does_not_leak() -> None:
    assert graph([("A", "B"), ("X", "Y"), ("Y", "Z")]).reachable("A") == frozenset({"B"})


def test_g3_diamond_has_no_duplicates() -> None:
    assert graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]).reachable("A") == frozenset(
        {"B", "C", "D"}
    )


def test_g3_returns_frozenset() -> None:
    assert isinstance(graph([("A", "B")]).reachable("A"), frozenset)


def test_g3_repeat_is_deterministic() -> None:
    g = graph([("A", "B"), ("B", "C"), ("A", "C")])
    assert g.reachable("A") == g.reachable("A") == frozenset({"B", "C"})


def test_g3_reverse_direction_is_not_reachable() -> None:
    assert graph([("A", "B")]).reachable("B") == frozenset()


def test_g3_partial_branch() -> None:
    assert graph([("A", "B"), ("A", "C"), ("C", "D")]).reachable("B") == frozenset()


def test_g3_long_chain() -> None:
    edges = [(str(i), str(i + 1)) for i in range(20)]
    assert len(graph(edges).reachable("0")) == 20


def test_g3_branching_chain() -> None:
    edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "E"), ("D", "F"), ("E", "F")]
    assert graph(edges).reachable("A") == frozenset({"B", "C", "D", "E", "F"})


@pytest.mark.exp19_perf
def test_g4_large_graph_is_linear_scale() -> None:
    edges = [(str(i), str(i + 1)) for i in range(10_000)]
    edges.extend((str(i), str(i + 10_000)) for i in range(10_000))
    g = graph(edges)
    start_wall = time.perf_counter()
    start_cpu = time.process_time()

    acyclic_start_wall = time.perf_counter()
    acyclic_start_cpu = time.process_time()
    assert g.is_acyclic() is True
    acyclic_end_wall = time.perf_counter()
    acyclic_end_cpu = time.process_time()

    reachable_start_wall = time.perf_counter()
    reachable_start_cpu = time.process_time()
    g.reachable("0")
    reachable_end_wall = time.perf_counter()
    reachable_end_cpu = time.process_time()

    end_wall = time.perf_counter()
    end_cpu = time.process_time()
    is_acyclic_wall_ms = (acyclic_end_wall - acyclic_start_wall) * 1000.0
    is_acyclic_cpu_ms = (acyclic_end_cpu - acyclic_start_cpu) * 1000.0
    reachable_wall_ms = (reachable_end_wall - reachable_start_wall) * 1000.0
    reachable_cpu_ms = (reachable_end_cpu - reachable_start_cpu) * 1000.0
    wall_ms = (end_wall - start_wall) * 1000.0
    cpu_ms = (end_cpu - start_cpu) * 1000.0
    warnings.warn(
        (
            "[G4_SPLIT_TELEMETRY] "
            f"is_acyclic_wall_ms={is_acyclic_wall_ms:.3f} | "
            f"is_acyclic_cpu_ms={is_acyclic_cpu_ms:.3f} | "
            f"reachable_wall_ms={reachable_wall_ms:.3f} | "
            f"reachable_cpu_ms={reachable_cpu_ms:.3f} | "
            f"composite_wall_ms={wall_ms:.3f} | "
            f"composite_cpu_ms={cpu_ms:.3f} | "
            f"non_cpu_delta_ms={wall_ms - cpu_ms:.3f}"
        ),
        UserWarning,
        stacklevel=1,
    )
    assert (wall_ms / 1000.0) <= 0.015


def test_g4_large_reachability_has_expected_size() -> None:
    edges = [(str(i), str(i + 1)) for i in range(19_999)]
    assert len(graph(edges).reachable("0")) == 19_999


def test_g4_sparse_components_scale() -> None:
    edges = [(str(i), str(i + 1)) for i in range(5_000)]
    edges.extend((f"x{i}", f"y{i}") for i in range(5_000))
    assert graph(edges).is_acyclic() is True


def test_g4_reachability_visits_only_component() -> None:
    edges = [(str(i), str(i + 1)) for i in range(5_000)]
    edges.extend((f"x{i}", f"y{i}") for i in range(5_000))
    assert len(graph(edges).reachable("0")) == 5_000


def test_g4_repeated_traversal_is_stable() -> None:
    g = graph([(str(i), str(i + 1)) for i in range(1_000)])
    assert g.reachable("0") == g.reachable("0")


def test_g5_core_isolation_modules() -> None:
    module = importlib.import_module("research.exp19.adjacency_graph")
    assert not any(name == "jamp" or name.startswith("jamp.") for name in module.__dict__)


def test_g5_core_isolation_import_scan() -> None:
    module = importlib.import_module("research.exp19.adjacency_graph")
    assert "/src/jamp/" not in module.__file__.replace("\\", "/")


def test_g5_base_relation_is_not_mutated() -> None:
    edge = relation("A", "B")
    before = edge
    graph([("A", "B")]).reachable("A")
    assert edge == before


def test_g5_graph_does_not_mutate_relation() -> None:
    edge = relation("A", "B")
    graph([("A", "B")]).is_acyclic()
    assert edge.source_id == "A" and edge.target_id == "B"


@pytest.mark.parametrize(
    "edges",
    [
        [("A", "B"), ("B", "C")],
        [("A", "B"), ("B", "C"), ("C", "D")],
        [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
        [("A", "B"), ("C", "D")],
        [("A", "B"), ("B", "D"), ("C", "D")],
    ],
)
def test_g5_no_core_runtime_dependency(edges: list[tuple[str, str]]) -> None:
    assert graph(edges).is_acyclic() is True
