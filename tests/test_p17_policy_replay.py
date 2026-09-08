"""P17.4 RED contract: causal fixation and deterministic policy replay."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from importlib import import_module

import pytest

from jamp.domain.event import EventNode, calculate_previous_graph_digest
from jamp.events.dag import EventDAG
from jamp.p17.dynamic_policy import PolicyWeights


def _modules():
    """Load the not-yet-implemented P17.4 modules at test execution time."""
    return (
        import_module("jamp.p17.policy_event"),
        import_module("jamp.p17.policy_replay"),
    )


def _weights(values: tuple[tuple[str, float], ...] = (("explore", 0.6), ("exploit", 0.4))) -> PolicyWeights:
    return PolicyWeights(values=values, total_budget=1.0, min_weight=0.1)


def _genesis() -> EventNode:
    dag = EventDAG()
    return dag.nodes[EventDAG.GENESIS_ID]


def _event_payload(prev: PolicyWeights, new: PolicyWeights) -> dict[str, object]:
    return {
        "prev_state_digest": prev.as_dict(),
        "new_state_digest": new.as_dict(),
        "evidence_digest": "e" * 64,
        "causal_source": "P17.3",
    }


def test_policy_update_event_encapsulates_state_evidence_and_parent() -> None:
    policy_event, _ = _modules()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))
    event = policy_event.PolicyUpdateEvent.create(
        event_id="POLICY_0001",
        parent_ids=(EventDAG.GENESIS_ID,),
        previous_state=previous,
        new_state=updated,
        evidence_digest="e" * 64,
        causal_source="P17.3",
    )

    assert event.parent_ids == (EventDAG.GENESIS_ID,)
    assert event.previous_state_digest == policy_event.policy_state_digest(previous)
    assert event.new_state_digest == policy_event.policy_state_digest(updated)
    assert event.evidence_digest == "e" * 64
    assert event.causal_source == "P17.3"


def test_causal_ordering_rejects_missing_or_out_of_order_parent() -> None:
    policy_event, _ = _modules()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))

    with pytest.raises(Exception):
        policy_event.PolicyUpdateEvent.create(
            event_id="POLICY_BAD_PARENT",
            parent_ids=("DOES_NOT_EXIST",),
            previous_state=previous,
            new_state=updated,
            evidence_digest="e" * 64,
            causal_source="P17.3",
        )


def test_previous_state_digest_mismatch_is_rejected() -> None:
    policy_event, _ = _modules()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))

    with pytest.raises(Exception):
        policy_event.PolicyUpdateEvent.create(
            event_id="POLICY_BAD_STATE",
            parent_ids=(EventDAG.GENESIS_ID,),
            previous_state=updated,
            new_state=previous,
            evidence_digest="e" * 64,
            causal_source="P17.3",
            previous_state_digest="0" * 64,
        )


def test_policy_update_event_is_fully_immutable() -> None:
    policy_event, _ = _modules()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))
    event = policy_event.PolicyUpdateEvent.create(
        event_id="POLICY_IMMUTABLE",
        parent_ids=(EventDAG.GENESIS_ID,),
        previous_state=previous,
        new_state=updated,
        evidence_digest="e" * 64,
        causal_source="P17.3",
    )

    with pytest.raises(FrozenInstanceError):
        event.evidence_digest = "x" * 64
    with pytest.raises(FrozenInstanceError):
        event.new_state_digest = "x" * 64


def test_replay_restores_policy_state_without_re_evaluation() -> None:
    policy_event, policy_replay = _modules()
    dag = EventDAG()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))
    event = policy_event.PolicyUpdateEvent.create(
        event_id="POLICY_REPLAY_0001",
        parent_ids=(EventDAG.GENESIS_ID,),
        previous_state=previous,
        new_state=updated,
        evidence_digest="e" * 64,
        causal_source="P17.3",
    )
    dag.nodes[event.event_id] = event
    dag.head_ids = [event.event_id]

    result = policy_replay.PolicyReplayEngine().replay(dag, genesis_state=previous)

    assert result.state == updated
    assert result.state_digest == policy_event.policy_state_digest(updated)
    assert result.event_ids == (EventDAG.GENESIS_ID, event.event_id)


def test_tampered_policy_history_triggers_integrity_error() -> None:
    policy_event, policy_replay = _modules()
    dag = EventDAG()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))
    event = policy_event.PolicyUpdateEvent.create(
        event_id="POLICY_TAMPER_0001",
        parent_ids=(EventDAG.GENESIS_ID,),
        previous_state=previous,
        new_state=updated,
        evidence_digest="e" * 64,
        causal_source="P17.3",
    )
    tampered = EventNode(
        event_id=event.event_id,
        event_type=event.event_type,
        payload={**dict(event.payload), "evidence_digest": "t" * 64},
        parent_ids=event.parent_ids,
        previous_graph_digest=calculate_previous_graph_digest((_genesis(),)),
        timestamp=event.timestamp,
    )
    dag.nodes[event.event_id] = tampered
    dag.head_ids = [event.event_id]

    with pytest.raises(Exception):
        policy_replay.PolicyReplayEngine().replay(dag, genesis_state=previous)


def test_replay_converges_deterministically_on_repeated_execution() -> None:
    policy_event, policy_replay = _modules()
    dag = EventDAG()
    previous = _weights()
    updated = _weights((("explore", 0.7), ("exploit", 0.3)))
    event = policy_event.PolicyUpdateEvent.create(
        event_id="POLICY_DETERMINISTIC_0001",
        parent_ids=(EventDAG.GENESIS_ID,),
        previous_state=previous,
        new_state=updated,
        evidence_digest="e" * 64,
        causal_source="P17.3",
    )
    dag.nodes[event.event_id] = event
    dag.head_ids = [event.event_id]
    engine = policy_replay.PolicyReplayEngine()

    first = engine.replay(dag, genesis_state=previous)
    second = engine.replay(dag, genesis_state=previous)

    assert first.state == second.state
    assert first.event_ids == second.event_ids
    assert first.state_digest == second.state_digest
