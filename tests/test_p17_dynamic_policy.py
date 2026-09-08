"""Contract tests for P17.3 Dynamic Policy Adaptor."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from jamp.p17.dynamic_policy import DynamicPolicyAdaptor, PolicyWeights


def test_exploration_floor_is_strictly_enforced():
    weights = PolicyWeights.from_mapping({"mcts": 0.6, "bfs": 0.3, "llm": 0.1}, total_budget=1.0, min_weight=0.1)
    adaptor = DynamicPolicyAdaptor(weights)
    updated = adaptor.update({"mcts": 0.98, "bfs": 0.01, "llm": 0.01})
    assert all(value >= 0.1 for value in updated.values())


def test_budget_normalization_is_preserved():
    weights = PolicyWeights.from_mapping({"mcts": 0.6, "bfs": 0.3, "llm": 0.1}, total_budget=1.0, min_weight=0.1)
    adaptor = DynamicPolicyAdaptor(weights)
    updated = adaptor.update({"mcts": 9.0, "bfs": 2.0, "llm": 1.0})
    assert sum(updated.values()) == pytest.approx(1.0)


def test_invalid_floor_or_budget_is_rejected():
    with pytest.raises(ValueError, match="floor"):
        PolicyWeights.from_mapping({"a": 0.5, "b": 0.5}, total_budget=1.0, min_weight=0.6)
    with pytest.raises(ValueError, match="budget"):
        PolicyWeights.from_mapping({"a": 0.2, "b": 0.2}, total_budget=1.0, min_weight=0.1)


def test_exploitation_trap_preserves_diversity():
    weights = PolicyWeights.from_mapping({"mcts": 0.6, "bfs": 0.3, "llm": 0.1}, total_budget=1.0, min_weight=0.1)
    adaptor = DynamicPolicyAdaptor(weights)
    updated = adaptor.update({"mcts": 1.0, "bfs": 0.0, "llm": 0.0}, exploitation_pressure=1.0)
    assert updated["bfs"] > 0.1
    assert updated["llm"] > 0.1
    assert sum(updated.values()) == pytest.approx(1.0)


def test_policy_update_is_deterministic_and_stateless():
    weights = PolicyWeights.from_mapping({"mcts": 0.6, "bfs": 0.3, "llm": 0.1}, total_budget=1.0, min_weight=0.1)
    adaptor = DynamicPolicyAdaptor(weights)
    evidence = {"mcts": 0.8, "bfs": 0.4, "llm": 0.2}
    before = dict(vars(adaptor))
    first = adaptor.update(evidence, exploitation_pressure=0.2)
    after_first = dict(vars(adaptor))
    second = adaptor.update(evidence, exploitation_pressure=0.2)
    after_second = dict(vars(adaptor))

    assert first == second
    assert before == after_first == after_second
    assert all(isinstance(value, PolicyWeights) for value in vars(adaptor).values())
    with pytest.raises(FrozenInstanceError):
        adaptor._weights = weights


def test_unknown_policy_is_rejected():
    weights = PolicyWeights.from_mapping({"mcts": 0.6, "bfs": 0.4}, total_budget=1.0, min_weight=0.1)
    adaptor = DynamicPolicyAdaptor(weights)
    with pytest.raises(ValueError, match="policy"):
        adaptor.update({"mcts": 0.5, "bfs": 0.3, "llm": 0.2})
