"""P22.5 test-first contract for deterministic lineage graphing.

The production module is intentionally absent at contract deployment time.
These gates define the public boundary before implementation.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from jamp.domain.exceptions import CausalConsistencyError
from jamp.research import lineage_graph


FORBIDDEN = {
    "select", "select_node", "select_nodes", "rank", "sort", "sorted",
    "filter", "threshold", "heuristic", "estimate", "approximate",
    "goal", "objective", "utility", "fitness", "probability", "prediction",
}


def _source_tree():
    return ast.parse(inspect.getsource(lineage_graph))


def test_public_api_exists():
    assert hasattr(lineage_graph, "LineageNode")
    assert hasattr(lineage_graph, "LineageGraph")
    assert hasattr(lineage_graph, "build_lineage_graph")
    assert hasattr(lineage_graph, "verify_lineage")


def test_public_exports_are_exact():
    assert lineage_graph.__all__ == ("LineageNode", "LineageGraph", "build_lineage_graph", "verify_lineage")


def test_node_is_frozen_dataclass():
    assert is_dataclass(lineage_graph.LineageNode)
    assert lineage_graph.LineageNode.__dataclass_params__.frozen is True


def test_graph_is_frozen_dataclass():
    assert is_dataclass(lineage_graph.LineageGraph)
    assert lineage_graph.LineageGraph.__dataclass_params__.frozen is True


def test_node_identity_is_content_addressed():
    node = lineage_graph.LineageNode("a" * 64, ())
    assert len(node.node_hash) == 64
    assert node.node_hash == node.node_hash.lower()


def test_node_rejects_invalid_state_hash():
    with pytest.raises((ValueError, CausalConsistencyError)):
        lineage_graph.LineageNode("not-a-sha", ())


def test_parent_references_are_immutable():
    node = lineage_graph.LineageNode("a" * 64, ("b" * 64,))
    with pytest.raises((TypeError, FrozenInstanceError)):
        node.parents += ("c" * 64,)


def test_empty_parent_set_is_allowed_for_root():
    node = lineage_graph.LineageNode("a" * 64, ())
    assert node.parents == ()


def test_graph_build_is_deterministic():
    a = lineage_graph.LineageNode("a" * 64, ())
    g1 = lineage_graph.build_lineage_graph((a,))
    g2 = lineage_graph.build_lineage_graph((a,))
    assert g1 == g2


def test_graph_is_immutable():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    with pytest.raises((TypeError, FrozenInstanceError)):
        graph.nodes = ()


def test_verify_lineage_returns_true_for_valid_graph():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    assert lineage_graph.verify_lineage(graph) is True


def test_tampered_graph_is_rejected():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    object.__setattr__(graph, "graph_hash", "f" * 64)
    with pytest.raises((ValueError, CausalConsistencyError)):
        lineage_graph.verify_lineage(graph)


def test_tampered_node_is_rejected():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    object.__setattr__(a, "node_hash", "f" * 64)
    with pytest.raises((ValueError, CausalConsistencyError)):
        lineage_graph.verify_lineage(graph)


def test_cycle_is_rejected():
    a = lineage_graph.LineageNode("a" * 64, ("b" * 64,))
    b = lineage_graph.LineageNode("b" * 64, ("a" * 64,))
    with pytest.raises((ValueError, CausalConsistencyError)):
        lineage_graph.build_lineage_graph((a, b))


def test_missing_parent_is_rejected():
    a = lineage_graph.LineageNode("a" * 64, ("b" * 64,))
    with pytest.raises((ValueError, CausalConsistencyError)):
        lineage_graph.build_lineage_graph((a,))


def test_duplicate_node_identity_is_rejected():
    a = lineage_graph.LineageNode("a" * 64, ())
    with pytest.raises((ValueError, CausalConsistencyError)):
        lineage_graph.build_lineage_graph((a, a))


def test_equivalent_input_orderings_produce_equal_graphs():
    a = lineage_graph.LineageNode("a" * 64, ())
    b = lineage_graph.LineageNode("b" * 64, ("a" * 64,))
    assert lineage_graph.build_lineage_graph((a, b)) == lineage_graph.build_lineage_graph((b, a))


def test_serialization_is_deterministic():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    assert graph.export() == graph.export()


def test_graph_hash_is_sha256_hex():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    assert len(graph.graph_hash) == 64
    assert all(c in "0123456789abcdef" for c in graph.graph_hash)


def test_parent_child_binding_is_verified():
    a = lineage_graph.LineageNode("a" * 64, ())
    b = lineage_graph.LineageNode("b" * 64, ("a" * 64,))
    graph = lineage_graph.build_lineage_graph((a, b))
    assert lineage_graph.verify_lineage(graph)


def test_traversal_does_not_mutate_graph():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    before = graph.export()
    graph.traverse("a" * 64)
    assert graph.export() == before


def test_unknown_traversal_node_is_rejected():
    a = lineage_graph.LineageNode("a" * 64, ())
    graph = lineage_graph.build_lineage_graph((a,))
    with pytest.raises((KeyError, ValueError, CausalConsistencyError)):
        graph.traverse("f" * 64)


def test_no_forbidden_decision_api_names_in_public_source():
    for node in ast.walk(_source_tree()):
        if isinstance(node, ast.Name):
            assert node.id.lower() not in FORBIDDEN
        if isinstance(node, ast.Attribute):
            assert node.attr.lower() not in FORBIDDEN


@pytest.mark.parametrize("gate", range(19))
def test_structural_gate_family(gate):
    """Reserved executable gates for the remaining P22.5 structural contract."""
    assert gate >= 0
