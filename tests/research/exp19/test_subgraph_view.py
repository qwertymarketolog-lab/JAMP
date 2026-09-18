from __future__ import annotations

import pytest

from research.exp19.adjacency_graph import ObservationAdjacencyGraph
from research.exp19.observation_relation import ObservationRelation


@pytest.fixture
def base_graph() -> tuple[
    ObservationAdjacencyGraph,
    ObservationRelation,
    ObservationRelation,
    ObservationRelation,
]:
    r1 = ObservationRelation(
        source_id="node_a", target_id="node_b", relation_type="DEP", params={}
    )
    r2 = ObservationRelation(
        source_id="node_b", target_id="node_c", relation_type="REF", params={}
    )
    r3 = ObservationRelation(
        source_id="node_c", target_id="node_d", relation_type="DEP", params={}
    )
    return ObservationAdjacencyGraph((r1, r2, r3)), r1, r2, r3


def test_subgraph_view_filters_by_relation_type(
    base_graph: tuple[
        ObservationAdjacencyGraph,
        ObservationRelation,
        ObservationRelation,
        ObservationRelation,
    ],
) -> None:
    graph, r1, r2, r3 = base_graph
    view = graph.subgraph_view("DEP")

    assert isinstance(view, ObservationAdjacencyGraph)
    assert view.is_acyclic()
    assert view.reachable("node_a") == frozenset({"node_b"})
    assert view.reachable("node_c") == frozenset({"node_d"})


def test_subgraph_view_zero_object_duplication(
    base_graph: tuple[
        ObservationAdjacencyGraph,
        ObservationRelation,
        ObservationRelation,
        ObservationRelation,
    ],
) -> None:
    graph, r1, r2, r3 = base_graph
    view = graph.subgraph_view("DEP")

    view_edges = tuple(view._edges.values())
    assert len(view_edges) == 2
    assert any(edge is r1 for edge in view_edges)
    assert any(edge is r3 for edge in view_edges)
    assert all(edge is not r2 for edge in view_edges)


def test_subgraph_view_is_immutable_and_does_not_mutate_base(
    base_graph: tuple[
        ObservationAdjacencyGraph,
        ObservationRelation,
        ObservationRelation,
        ObservationRelation,
    ],
) -> None:
    graph, r1, r2, r3 = base_graph
    base_edges = dict(graph._edges)
    view = graph.subgraph_view("DEP")

    with pytest.raises((AttributeError, TypeError)):
        view._edges["e99"] = r1  # type: ignore[index]

    assert graph._edges == base_edges
    assert graph.reachable("node_a") == frozenset({"node_b", "node_c", "node_d"})


def test_subgraph_view_does_not_duplicate_relations_when_reused(
    base_graph: tuple[
        ObservationAdjacencyGraph,
        ObservationRelation,
        ObservationRelation,
        ObservationRelation,
    ],
) -> None:
    graph, r1, r2, r3 = base_graph

    dep_view = graph.subgraph_view("DEP")
    dep_view_again = graph.subgraph_view("DEP")

    assert tuple(dep_view._edges.values()) == tuple(dep_view_again._edges.values())
    assert all(
        left is right
        for left, right in zip(
            dep_view._edges.values(), dep_view_again._edges.values(), strict=True
        )
    )
    assert tuple(dep_view._edges.values()) == (r1, r3)
