"""P17.5 RED contract tests: policy-guided Search integration."""

import hashlib
import json

import pytest

from jamp.p17.dynamic_policy import DynamicPolicyAdaptor, PolicyWeights
from jamp.p17.policy_event import PolicyUpdateEvent, policy_state_digest
from jamp.p17.policy_replay import PolicyReplayEngine
from jamp.p17.policy_guided_search import PolicyGuidedSearch
from jamp.registry import EventDAG


def _weights():
    return PolicyWeights.from_mapping(
        {"explore": 0.6, "exploit": 0.4}, total_budget=1.0, min_weight=0.1
    )


def _policy_event(dag, old_state, new_state):
    evidence = hashlib.sha256(b"p17.5-evidence").hexdigest()
    return PolicyUpdateEvent.create(
        event_id="POLICY_P175_1",
        parent_ids=[EventDAG.GENESIS_ID],
        previous_state=old_state,
        new_state=new_state,
        evidence_digest=evidence,
        causal_source="p17.3",
        dag=dag,
    )


def test_policy_guided_search_is_deterministic():
    search = PolicyGuidedSearch()
    policy = _weights()
    assert search.run("GENESIS", policy) == search.run("GENESIS", policy)


def test_policy_is_explicitly_injected_and_search_does_not_recalculate_it():
    search = PolicyGuidedSearch()
    policy = _weights()
    adaptor = DynamicPolicyAdaptor(policy)
    with pytest.raises(AttributeError):
        search.update_policy(adaptor)
    result = search.run("GENESIS", policy)
    assert result.policy_digest == policy_state_digest(policy)


def test_search_behavior_is_causally_attributed_to_policy_event():
    dag = EventDAG()
    old_state = _weights()
    new_state = PolicyWeights.from_mapping(
        {"explore": 0.8, "exploit": 0.2}, total_budget=1.0, min_weight=0.1
    )
    event = _policy_event(dag, old_state, new_state)
    dag.nodes[event.event_id] = event
    result = PolicyGuidedSearch().run("GENESIS", new_state, policy_event=event)
    assert result.policy_event_id == event.event_id
    assert result.policy_digest == event.new_state_digest


def test_completed_trajectory_is_not_retroactively_modified():
    search = PolicyGuidedSearch()
    first = search.run("GENESIS", _weights())
    second = search.run(
        "GENESIS",
        PolicyWeights.from_mapping(
            {"explore": 0.9, "exploit": 0.1}, total_budget=1.0, min_weight=0.1
        ),
    )
    assert first.trajectory_digest != second.trajectory_digest
    assert first.trajectory_digest == search.run("GENESIS", _weights()).trajectory_digest


def test_replay_restores_the_policy_state_used_by_search():
    dag = EventDAG()
    old_state = _weights()
    new_state = PolicyWeights.from_mapping(
        {"explore": 0.7, "exploit": 0.3}, total_budget=1.0, min_weight=0.1
    )
    event = _policy_event(dag, old_state, new_state)
    dag.nodes[event.event_id] = event
    replay = PolicyReplayEngine().replay(dag, genesis_state=old_state)
    result = PolicyGuidedSearch().run("GENESIS", replay.state, policy_event=event)
    assert result.policy_digest == replay.state_digest


def test_exploration_floor_survives_search_integration():
    policy = PolicyWeights.from_mapping(
        {"explore": 0.9, "exploit": 0.1}, total_budget=1.0, min_weight=0.1
    )
    result = PolicyGuidedSearch().run("GENESIS", policy)
    assert all(value >= policy.min_weight for value in result.effective_weights.values())


def test_search_result_contains_canonical_policy_binding():
    policy = _weights()
    result = PolicyGuidedSearch().run("GENESIS", policy)
    payload = json.dumps(result.canonical_payload, sort_keys=True, separators=(",", ":"))
    assert result.trajectory_digest == hashlib.sha256(payload.encode()).hexdigest()
