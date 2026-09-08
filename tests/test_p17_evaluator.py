from __future__ import annotations

import random

import pytest

from jamp.domain.exceptions import ReadonlyStateError
from jamp.domain.replay import ReadonlyRegistry
from jamp.p17.evaluator import TrajectoryOutcomeEvaluator
from jamp.registry.registry import Registry, RegistryRecord


def _readonly_registry() -> ReadonlyRegistry:
    registry = Registry()
    token = registry._commit_authority()
    registry._commit_add(
        RegistryRecord(
            record_id="FACT_1",
            kind="fact",
            payload={"candidate_id": "1", "statement": "A"},
        ),
        token,
    )
    return ReadonlyRegistry.from_registry(registry)


def _trajectory(evaluator: TrajectoryOutcomeEvaluator) -> object:
    return evaluator.synthetic_trajectory(
        _readonly_registry(), depth=3, candidate_count=5, branching_burden=4
    )


def test_evaluator_cannot_mutate_registry() -> None:
    readonly = _readonly_registry()
    evaluator = TrajectoryOutcomeEvaluator()
    before = readonly.all()

    trajectory = evaluator.synthetic_trajectory(readonly, depth=1, candidate_count=1, branching_burden=0)
    evaluator.evaluate(trajectory)

    assert readonly.all() == before
    with pytest.raises(ReadonlyStateError):
        readonly.add(object())


def test_readonly_registry_immutability() -> None:
    readonly = _readonly_registry()
    before = readonly.all()

    with pytest.raises(ReadonlyStateError):
        readonly.add(object())

    assert readonly.all() == before


def test_deterministic_causal_efficiency() -> None:
    evaluator = TrajectoryOutcomeEvaluator()
    trajectory = _trajectory(evaluator)

    first = evaluator.evaluate(trajectory)
    second = evaluator.evaluate(trajectory)

    assert first == second
    assert first.causal_efficiency == second.causal_efficiency


def test_cost_structural_independence() -> None:
    evaluator = TrajectoryOutcomeEvaluator()
    trajectory = _trajectory(evaluator)

    baseline = evaluator.evaluate(trajectory)
    with_environment_metadata = evaluator.evaluate(
        trajectory,
        environment_metadata={"wall_clock_seconds": 9999, "peak_memory_bytes": 10**18},
    )

    assert baseline.cost == with_environment_metadata.cost
    assert baseline.causal_efficiency == with_environment_metadata.causal_efficiency


def test_nondeterministic_evaluator_rejection() -> None:
    class RandomizedEvaluator(TrajectoryOutcomeEvaluator):
        def evaluate(self, trajectory, environment_metadata=None):
            result = super().evaluate(trajectory, environment_metadata)
            return result.__class__(
                **{**result.__dict__, "causal_efficiency": result.causal_efficiency + random.random()}
            )

    evaluator = RandomizedEvaluator()
    with pytest.raises(Exception, match="Evaluator produced different results"):
        evaluator.assert_deterministic(_trajectory(evaluator))


def test_evaluator_digest_integrity() -> None:
    evaluator = TrajectoryOutcomeEvaluator()
    assert evaluator.validate_digest(evaluator.evaluator_digest)
    with pytest.raises(ValueError, match="digest"):
        evaluator.validate_digest("0" * 64)


def test_evaluator_has_no_hidden_mutable_state() -> None:
    evaluator = TrajectoryOutcomeEvaluator()
    trajectory = _trajectory(evaluator)
    before = dict(vars(evaluator))
    first = evaluator.evaluate(trajectory)
    second = evaluator.evaluate(trajectory)

    assert first == second
    assert dict(vars(evaluator)) == before == {}
