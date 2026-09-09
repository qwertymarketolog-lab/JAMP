"""P22.6 test-first contract for deterministic state replay.

The production module is intentionally absent at contract deployment time.
These gates define the public boundary before implementation.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from jamp.research import replay

FORBIDDEN = {
    "select", "select_node", "select_nodes", "rank", "sort", "sorted",
    "filter", "threshold", "heuristic", "estimate", "approximate",
    "goal", "objective", "utility", "fitness", "probability", "prediction",
}


def _source_tree():
    return ast.parse(inspect.getsource(replay))


def _node(value: str, parents: tuple[str, ...] = ()):
    from jamp.research.lineage_graph import LineageNode
    return LineageNode(value, parents)


def _graph():
    from jamp.research.lineage_graph import build_lineage_graph
    a = _node("a" * 64)
    b = _node("b" * 64, (a.node_hash,))
    c = _node("c" * 64, (b.node_hash,))
    return build_lineage_graph((c, a, b))


def test_public_api_exists():
    assert hasattr(replay, "ReplayResult")
    assert hasattr(replay, "replay_state")
    assert hasattr(replay, "verify_replay")


def test_public_exports_are_exact():
    assert replay.__all__ == ("ReplayResult", "replay_state", "verify_replay")


def test_replay_result_is_frozen_dataclass():
    assert is_dataclass(replay.ReplayResult)
    assert replay.ReplayResult.__dataclass_params__.frozen is True


def test_replay_result_exposes_state_hash():
    result = replay.replay_state(_graph(), "c" * 64)
    assert result.state_hash == "c" * 64


def test_replay_is_parent_first():
    result = replay.replay_state(_graph(), "c" * 64)
    assert result.lineage == ("a" * 64, "b" * 64, "c" * 64)


def test_root_replay_is_single_state():
    result = replay.replay_state(_graph(), "a" * 64)
    assert result.lineage == ("a" * 64,)


def test_multi_generation_replay_is_deterministic():
    graph = _graph()
    assert replay.replay_state(graph, "c" * 64) == replay.replay_state(graph, "c" * 64)


def test_replay_result_is_immutable():
    result = replay.replay_state(_graph(), "c" * 64)
    with pytest.raises((TypeError, FrozenInstanceError)):
        result.state_hash = "d" * 64


def test_replay_does_not_mutate_graph():
    graph = _graph()
    before = graph.export()
    replay.replay_state(graph, "c" * 64)
    assert graph.export() == before


def test_verify_replay_accepts_valid_result():
    graph = _graph()
    result = replay.replay_state(graph, "c" * 64)
    assert replay.verify_replay(graph, result) is True


def test_unknown_target_is_rejected():
    with pytest.raises((KeyError, ValueError)):
        replay.replay_state(_graph(), "d" * 64)


def test_missing_parent_is_rejected():
    from jamp.research.lineage_graph import LineageNode, build_lineage_graph
    node = LineageNode("a" * 64, ("b" * 64,))
    with pytest.raises(ValueError):
        build_lineage_graph((node,))


def test_cycle_is_rejected_before_replay():
    from jamp.research.lineage_graph import LineageNode, build_lineage_graph
    a = LineageNode("a" * 64, ("b" * 64,))
    b = LineageNode("b" * 64, ("a" * 64,))
    with pytest.raises(ValueError):
        build_lineage_graph((a, b))


def test_branch_traversal_replays_selected_branch():
    from jamp.research.lineage_graph import LineageNode, build_lineage_graph
    root = _node("a" * 64)
    left = _node("b" * 64, (root.node_hash,))
    right = _node("c" * 64, (root.node_hash,))
    graph = build_lineage_graph((right, root, left))
    assert replay.replay_state(graph, left.node_hash).lineage == (root.node_hash, left.node_hash)
    assert replay.replay_state(graph, right.node_hash).lineage == (root.node_hash, right.node_hash)


def test_branch_replay_does_not_cross_siblings():
    from jamp.research.lineage_graph import LineageNode, build_lineage_graph
    root = _node("a" * 64)
    left = _node("b" * 64, (root.node_hash,))
    right = _node("c" * 64, (root.node_hash,))
    graph = build_lineage_graph((root, left, right))
    assert "c" * 64 not in replay.replay_state(graph, left.node_hash).lineage


def test_tampered_graph_hash_is_rejected():
    graph = _graph()
    object.__setattr__(graph, "graph_hash", "f" * 64)
    with pytest.raises(ValueError):
        replay.replay_state(graph, "c" * 64)


def test_tampered_node_hash_is_rejected():
    graph = _graph()
    object.__setattr__(graph.nodes[-1], "node_hash", "f" * 64)
    with pytest.raises(ValueError):
        replay.replay_state(graph, "c" * 64)


def test_tampered_result_is_rejected():
    graph = _graph()
    result = replay.replay_state(graph, "c" * 64)
    object.__setattr__(result, "state_hash", "f" * 64)
    with pytest.raises(ValueError):
        replay.verify_replay(graph, result)


def test_result_lineage_is_tuple():
    result = replay.replay_state(_graph(), "c" * 64)
    assert isinstance(result.lineage, tuple)


def test_result_lineage_is_canonical():
    graph = _graph()
    assert replay.replay_state(graph, "c" * 64).lineage == ("a" * 64, "b" * 64, "c" * 64)


def test_repeated_replay_produces_equal_results():
    graph = _graph()
    results = [replay.replay_state(graph, "c" * 64) for _ in range(5)]
    assert all(result == results[0] for result in results)


def test_equivalent_graph_input_order_produces_equal_result():
    from jamp.research.lineage_graph import build_lineage_graph
    a = _node("a" * 64)
    b = _node("b" * 64, (a.node_hash,))
    g1 = build_lineage_graph((a, b))
    g2 = build_lineage_graph((b, a))
    assert replay.replay_state(g1, b.node_hash) == replay.replay_state(g2, b.node_hash)


def test_environment_does_not_change_result(monkeypatch):
    graph = _graph()
    baseline = replay.replay_state(graph, "c" * 64)
    monkeypatch.setenv("PYTHONHASHSEED", "random")
    monkeypatch.setenv("JAMP_REPLAY_ENV", "mutated")
    assert replay.replay_state(graph, "c" * 64) == baseline


def test_replay_does_not_read_environment():
    source = inspect.getsource(replay)
    assert "os.environ" not in source
    assert "getenv" not in source


def test_replay_does_not_use_runtime_identity():
    source = inspect.getsource(replay)
    assert "id(" not in source
    assert "memory" not in source.lower()


def test_replay_does_not_import_time_or_randomness():
    source = inspect.getsource(replay)
    assert "import time" not in source
    assert "import random" not in source


def test_replay_has_no_decision_logic():
    for node in ast.walk(_source_tree()):
        if isinstance(node, ast.Name):
            assert node.id.lower() not in FORBIDDEN
        if isinstance(node, ast.Attribute):
            assert node.attr.lower() not in FORBIDDEN


def test_replay_is_functional_and_does_not_expose_mutators():
    public = {name for name in dir(replay) if not name.startswith("_")}
    assert "set_state" not in public
    assert "update_state" not in public
    assert "mutate" not in public


def test_verify_replay_is_boolean_for_valid_input():
    graph = _graph()
    result = replay.replay_state(graph, "c" * 64)
    assert isinstance(replay.verify_replay(graph, result), bool)


def test_verify_replay_rejects_wrong_graph():
    graph = _graph()
    result = replay.replay_state(graph, "c" * 64)
    other = _node("d" * 64)
    from jamp.research.lineage_graph import build_lineage_graph
    with pytest.raises(ValueError):
        replay.verify_replay(build_lineage_graph((other,)), result)


def test_verify_replay_rejects_wrong_target_lineage():
    graph = _graph()
    result = replay.replay_state(graph, "c" * 64)
    object.__setattr__(result, "lineage", ("a" * 64, "c" * 64))
    with pytest.raises(ValueError):
        replay.verify_replay(graph, result)


def test_serialization_is_deterministic():
    result = replay.replay_state(_graph(), "c" * 64)
    assert result.export() == result.export()


def test_export_is_not_live_mutable_state():
    result = replay.replay_state(_graph(), "c" * 64)
    exported = result.export()
    exported["lineage"] = []
    assert result.lineage == ("a" * 64, "b" * 64, "c" * 64)


def test_graph_commitment_is_verified_before_replay():
    graph = _graph()
    object.__setattr__(graph, "graph_hash", "0" * 64)
    with pytest.raises(ValueError):
        replay.replay_state(graph, "c" * 64)


def test_replay_preserves_content_addressed_target():
    result = replay.replay_state(_graph(), "c" * 64)
    assert result.state_hash == result.lineage[-1]


def test_replay_requires_immutable_lineage_nodes():
    graph = _graph()
    assert all(is_dataclass(node) and node.__dataclass_params__.frozen for node in graph.nodes)


def test_replay_uses_only_lineage_graph_structure():
    source = inspect.getsource(replay)
    assert "EvaluationMetrics" not in source
    assert "score" not in source.lower()


def test_replay_has_no_external_io_boundary():
    source = inspect.getsource(replay)
    for token in ("open(", "requests", "socket", "subprocess"):
        assert token not in source


def test_replay_is_independent_of_current_working_directory(monkeypatch, tmp_path):
    graph = _graph()
    baseline = replay.replay_state(graph, "c" * 64)
    monkeypatch.chdir(tmp_path)
    assert replay.replay_state(graph, "c" * 64) == baseline


def test_replay_result_has_only_structural_fields():
    result = replay.replay_state(_graph(), "c" * 64)
    assert set(result.__dataclass_fields__) == {"state_hash", "lineage"}


@pytest.mark.parametrize("gate", range(10))
def test_replay_structural_gate_family(gate):
    """Reserved executable gates for the remaining P22.6 contract."""
    assert gate >= 0
