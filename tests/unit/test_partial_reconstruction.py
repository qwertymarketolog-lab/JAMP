"""P16.4 partial state reconstruction and time-travel invariants."""
from __future__ import annotations

from dataclasses import replace

import pytest

from jamp.domain.event import EventNode, calculate_previous_graph_digest
from jamp.domain.exceptions import (
    CausalConsistencyError,
    EventNotFoundError,
    ReadonlyStateError,
)
from jamp.domain.replay import ReadonlyRegistry, ReplayEngine
from jamp.events.dag import EventDAG


def _fact_payload(candidate_id: str, statement: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "statement": statement,
        "status": "CONFIRMED",
        "provenance": {"source": "test"},
    }


def _append_branch(
    dag: EventDAG,
    event_id: str,
    parent_id: str,
    candidate_id: str,
    statement: str,
    timestamp: float,
) -> EventNode:
    node = EventNode(
        event_id=event_id,
        event_type="FactCommitted",
        payload=_fact_payload(candidate_id, statement),
        parent_ids=(parent_id,),
        previous_graph_digest=calculate_previous_graph_digest((dag.nodes[parent_id],)),
        timestamp=timestamp,
    )
    dag.nodes[event_id] = node
    return node


def test_replay_until_filters_unrelated_parallel_branch() -> None:
    dag = EventDAG()
    first = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    target = _append_branch(dag, "EVT_TARGET", first.event_id, "B", "beta", 2.0)
    _append_branch(dag, "EVT_PARALLEL", EventDAG.GENESIS_ID, "C", "gamma", 3.0)

    result = ReplayEngine().replay_until(dag, target.event_id)

    assert result.verified is True
    assert result.event_ids == (EventDAG.GENESIS_ID, first.event_id, target.event_id)
    assert result.registry.facts == frozenset({"alpha", "beta"})
    assert "gamma" not in result.registry.facts
    assert isinstance(result.registry, ReadonlyRegistry)


def test_replay_until_genesis_returns_empty_snapshot() -> None:
    result = ReplayEngine().replay_until(EventDAG(), EventDAG.GENESIS_ID)

    assert result.event_ids == (EventDAG.GENESIS_ID,)
    assert result.registry.all() == ()
    assert result.registry.facts == frozenset()


def test_invalid_target_fails_before_reconstruction() -> None:
    dag = EventDAG()
    dag.append_event("FactCommitted", _fact_payload("A", "alpha"))

    with pytest.raises(EventNotFoundError, match="missing-event"):
        ReplayEngine().replay_until(dag, "missing-event")


def test_historical_snapshot_rejects_mutation() -> None:
    dag = EventDAG()
    target = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    snapshot = ReplayEngine().replay_until(dag, target.event_id).registry

    with pytest.raises(ReadonlyStateError):
        snapshot.add(object())

    with pytest.raises(ReadonlyStateError):
        snapshot._commit_add(object(), object())


def test_historical_payload_is_deeply_readonly() -> None:
    dag = EventDAG()
    target = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    snapshot = ReplayEngine().replay_until(dag, target.event_id).registry
    record = snapshot.all()[0]

    with pytest.raises(TypeError):
        record.payload["statement"] = "tampered"  # type: ignore[index]

    provenance = record.payload["provenance"]
    with pytest.raises(TypeError):
        provenance["source"] = "tampered"  # type: ignore[index]


def test_replay_until_rejects_tampered_source_before_snapshot_creation() -> None:
    dag = EventDAG()
    target = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    dag.nodes[target.event_id] = replace(
        target,
        payload=_fact_payload("A", "tampered"),
    )

    with pytest.raises(CausalConsistencyError):
        ReplayEngine().replay_until(dag, target.event_id)


def test_replay_until_is_independent_of_storage_order() -> None:
    dag = EventDAG()
    first = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    target = _append_branch(dag, "EVT_TARGET", first.event_id, "B", "beta", 2.0)
    parallel = _append_branch(
        dag, "EVT_PARALLEL", EventDAG.GENESIS_ID, "C", "gamma", 3.0
    )

    result_a = ReplayEngine().replay_until(dag, target.event_id)
    # I2 requires each parent to precede its child. Only the unrelated
    # concurrent sibling is moved, preserving a valid topological storage order.
    dag.nodes = {
        EventDAG.GENESIS_ID: dag.nodes[EventDAG.GENESIS_ID],
        first.event_id: first,
        parallel.event_id: parallel,
        target.event_id: target,
    }
    result_b = ReplayEngine().replay_until(dag, target.event_id)

    assert result_a.state_digest == result_b.state_digest
    assert result_a.event_ids == result_b.event_ids
    assert result_a.registry.all() == result_b.registry.all()
