"""P16.3 deterministic replay and zero-divergence tests."""
from __future__ import annotations

from dataclasses import replace

import pytest

from jamp.domain.exceptions import CausalConsistencyError
from jamp.domain.replay import ReplayEngine
from jamp.events.dag import EventDAG
from jamp.registry.registry import Registry, RegistryRecord


def _fact_payload(candidate_id: str, statement: str) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "statement": statement,
        "status": "CONFIRMED",
        "provenance": {"source": "test"},
    }


def _reference_registry(dag: EventDAG) -> Registry:
    registry = Registry()
    token = registry._commit_authority()
    for event in dag.nodes.values():
        if event.event_type == "FactCommitted":
            payload = dict(event.payload)
            registry._commit_add(
                RegistryRecord(
                    record_id=f"FACT_{payload['candidate_id']}",
                    kind="fact",
                    payload={
                        "candidate_id": payload["candidate_id"],
                        "statement": payload["statement"],
                        "source_id": payload.get("source_id", ""),
                        "provenance": payload.get("provenance", {}),
                    },
                ),
                token,
            )
    return registry


def test_zero_divergence_against_incremental_reference() -> None:
    dag = EventDAG()
    dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    dag.append_event("FactCommitted", _fact_payload("B", "beta"))

    result = ReplayEngine().replay(dag, expected_registry=_reference_registry(dag))

    assert result.verified is True
    assert result.zero_divergence is True
    assert result.registry.facts == frozenset({"alpha", "beta"})


def test_replay_is_independent_of_concurrent_storage_order() -> None:
    dag = EventDAG()
    first = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))

    # Build a second branch from Genesis so both events are causally independent.
    second = replace(
        dag.append_event("FactRejected", {"candidate_id": "TEMP", "statement": "unused"}),
        event_id="EVT_BRANCH",
        parent_ids=(EventDAG.GENESIS_ID,),
    )
    # The replacement above is deliberately rebuilt with a valid canonical digest.
    from jamp.domain.event import EventNode, calculate_previous_graph_digest

    second = EventNode(
        event_id=second.event_id,
        event_type="FactCommitted",
        payload=_fact_payload("B", "beta"),
        parent_ids=(EventDAG.GENESIS_ID,),
        previous_graph_digest=calculate_previous_graph_digest(
            (dag.nodes[EventDAG.GENESIS_ID],)
        ),
        timestamp=2.0,
    )
    dag.nodes = {
        EventDAG.GENESIS_ID: dag.nodes[EventDAG.GENESIS_ID],
        second.event_id: second,
        first.event_id: first,
    }

    result_a = ReplayEngine().replay(dag)
    dag.nodes = {
        EventDAG.GENESIS_ID: dag.nodes[EventDAG.GENESIS_ID],
        first.event_id: first,
        second.event_id: second,
    }
    result_b = ReplayEngine().replay(dag)

    assert result_a.state_digest == result_b.state_digest
    assert result_a.registry.all() == result_b.registry.all()


def test_corrupted_payload_fails_before_replay_mutation() -> None:
    dag = EventDAG()
    event = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    dag.nodes[event.event_id] = replace(event, payload={"candidate_id": "A", "statement": "tampered"})

    with pytest.raises(CausalConsistencyError):
        ReplayEngine().replay(dag)


def test_corrupted_previous_graph_digest_fails_before_replay_mutation() -> None:
    dag = EventDAG()
    event = dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    dag.nodes[event.event_id] = replace(event, previous_graph_digest="0" * 64)

    with pytest.raises(CausalConsistencyError):
        ReplayEngine().replay(dag)


def test_replay_does_not_mutate_source_dag() -> None:
    dag = EventDAG()
    dag.append_event("FactCommitted", _fact_payload("A", "alpha"))
    before = dict(dag.nodes)

    ReplayEngine().replay(dag)

    assert dag.nodes == before
