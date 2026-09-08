"""P16.1 formal EventDAG consistency and negative invariants."""
from dataclasses import replace

import pytest

from jamp.domain import DAGConsistencyChecker, EventNode, CausalConsistencyError
from jamp.domain.event import calculate_previous_graph_digest, calculate_state_digest, sha256_text
from jamp.events.dag import EventDAG
from jamp.registry import Registry


def valid_dag() -> EventDAG:
    dag = EventDAG()
    dag.append_event("A", {"value": 1})
    dag.append_event("B", {"value": 2})
    DAGConsistencyChecker.validate(dag.nodes)
    return dag


def test_p16_1_valid_dag_passes() -> None:
    dag = valid_dag()
    assert tuple(dag.nodes) == ("GENESIS", "EVT_0001", "EVT_0002")


def test_p16_1_missing_parent_is_rejected() -> None:
    dag = valid_dag()
    node = dag.nodes["EVT_0002"]
    tampered = replace(node, parent_ids=("MISSING",))
    nodes = dict(dag.nodes)
    nodes[node.event_id] = tampered

    with pytest.raises(CausalConsistencyError, match="I2"):
        DAGConsistencyChecker.validate(nodes)


def test_p16_1_parent_order_is_rejected() -> None:
    dag = EventDAG()
    genesis = dag.nodes["GENESIS"]
    genesis_digest = calculate_previous_graph_digest((genesis,))
    parent_a = EventNode("A_PARENT", "A", {}, ("GENESIS",), "", genesis_digest, 0.0)
    parent_b = EventNode("B_PARENT", "B", {}, ("GENESIS",), "", genesis_digest, 0.0)
    nodes = {"GENESIS": genesis, "A_PARENT": parent_a, "B_PARENT": parent_b}
    child_previous = calculate_previous_graph_digest((parent_b, parent_a))
    child = EventNode("CHILD", "C", {}, ("B_PARENT", "A_PARENT"), "", child_previous, 0.0)
    nodes[child.event_id] = child

    with pytest.raises(CausalConsistencyError, match="I5"):
        DAGConsistencyChecker.validate(nodes)


def test_p16_1_cycle_is_rejected() -> None:
    a = EventNode("A", "A", {}, ("B",), calculate_state_digest({}), sha256_text("[]"), 0.0)
    b = EventNode("B", "B", {}, ("A",), calculate_state_digest({}), sha256_text("[]"), 0.0)
    with pytest.raises(CausalConsistencyError, match="I3"):
        DAGConsistencyChecker._acyclic({"A": a, "B": b})


def test_p16_1_state_tampering_is_rejected() -> None:
    dag = valid_dag()
    original = dag.nodes["EVT_0001"]
    tampered = replace(original, state_digest=sha256_text("forged-state"))
    nodes = dict(dag.nodes)
    nodes[original.event_id] = tampered

    with pytest.raises(CausalConsistencyError, match="I6/I7"):
        DAGConsistencyChecker.validate(nodes)


def test_p16_1_payload_tampering_breaks_hash_chain() -> None:
    dag = valid_dag()
    original = dag.nodes["EVT_0001"]
    tampered = replace(original, payload={"value": 999})
    nodes = dict(dag.nodes)
    nodes[original.event_id] = tampered

    with pytest.raises(CausalConsistencyError, match="I6/I7"):
        DAGConsistencyChecker.validate(nodes)


def test_p16_1_zero_registry_mutation_on_failure() -> None:
    dag = valid_dag()
    registry = Registry()
    before = registry.all()
    node = dag.nodes["EVT_0002"]
    nodes = dict(dag.nodes)
    nodes[node.event_id] = replace(node, state_digest=sha256_text("forged"))

    with pytest.raises(CausalConsistencyError):
        DAGConsistencyChecker.validate(nodes)

    assert registry.all() == before


def test_p16_1_event_nodes_are_immutable() -> None:
    dag = valid_dag()
    with pytest.raises(AttributeError):
        dag.nodes["EVT_0001"].event_id = "FORGED"  # type: ignore[misc]
