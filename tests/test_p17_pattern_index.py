"""RED contract tests for P17.2 Cross-Session Pattern Index."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from jamp.domain.exceptions import CausalConsistencyError, ReadonlyStateError
from jamp.domain.replay import ReadonlyRegistry
from jamp.p17.evaluator import TrajectoryOutcomeEvaluator
from jamp.p17.pattern_index import PatternIndex, PatternRecord


def _registry() -> ReadonlyRegistry:
    return ReadonlyRegistry(())


def _trajectory(*, statement: str = "A", success: bool = True):
    evaluator = TrajectoryOutcomeEvaluator()
    registry = _registry()
    trajectory = evaluator.synthetic_trajectory(
        registry,
        depth=3,
        candidate_count=4,
        branching_burden=2,
    )
    # Keep the fixture immutable while allowing distinct state/path identities.
    from dataclasses import replace

    return replace(
        trajectory,
        delta_progress=1.0 if success else 0.0,
        outcome_quality=1.0 if success else 0.0,
        causal_parents={
            "c0": (),
            "c1": ("c0",),
            "c2": ("c1",),
            "c3": ("c2",),
        },
        candidate_graph={
            "c0": ("c1",),
            "c1": ("c2",),
            "c2": ("c3",),
            "c3": (),
        },
    )


def test_pattern_index_is_deterministic():
    indexer = PatternIndex()
    trajectory = _trajectory()
    evaluator = TrajectoryOutcomeEvaluator()

    first = indexer.index(trajectory, evaluator)
    second = indexer.index(trajectory, evaluator)

    assert first == second
    assert first.pattern_key.causal_sequence_digest
    assert first.pattern_key.evaluator_digest == evaluator.evaluator_digest


def test_same_state_different_causal_path_produces_different_pattern():
    indexer = PatternIndex()
    evaluator = TrajectoryOutcomeEvaluator()

    first = indexer.index(_trajectory(), evaluator)
    from dataclasses import replace

    alternative = replace(
        _trajectory(),
        causal_parents={
            "c0": (),
            "c1": ("c0",),
            "c2": ("c0",),
            "c3": ("c1", "c2"),
        },
    )
    second = indexer.index(alternative, evaluator)

    assert first.pattern_key.state_digest == second.pattern_key.state_digest
    assert first.pattern_key.causal_sequence_digest != second.pattern_key.causal_sequence_digest
    assert first.pattern_key != second.pattern_key


def test_evaluator_digest_is_mandatory_and_bound():
    indexer = PatternIndex()
    evaluator = TrajectoryOutcomeEvaluator()

    with pytest.raises(ValueError, match="digest"):
        indexer.index(_trajectory(), evaluator, evaluator_digest="corrupted")


def test_pattern_record_is_immutable():
    record = PatternIndex().index(_trajectory(), TrajectoryOutcomeEvaluator())

    with pytest.raises(FrozenInstanceError):
        record.success = False


def test_indexing_cannot_mutate_readonly_registry():
    registry = _registry()
    indexer = PatternIndex()
    evaluator = TrajectoryOutcomeEvaluator()
    trajectory = _trajectory()

    before = registry.all()
    result = indexer.index(trajectory, evaluator)

    assert result
    assert registry.all() == before
    with pytest.raises(ReadonlyStateError):
        registry.add(object())


def test_failed_trajectory_is_marked_as_anti_pattern():
    record = PatternIndex().index(
        _trajectory(success=False),
        TrajectoryOutcomeEvaluator(),
    )

    assert record.anti_pattern is True
    assert record.success is False


def test_successful_trajectory_is_not_an_anti_pattern():
    record = PatternIndex().index(_trajectory(success=True), TrajectoryOutcomeEvaluator())

    assert record.success is True
    assert record.anti_pattern is False


def test_ranking_uses_causal_efficiency_then_digest():
    indexer = PatternIndex()
    evaluator = TrajectoryOutcomeEvaluator()
    records = [
        indexer.index(_trajectory(success=True), evaluator),
        indexer.index(_trajectory(success=False), evaluator),
    ]

    ranked = indexer.rank(records)
    assert ranked == tuple(sorted(records, key=lambda r: (-r.causal_efficiency, r.pattern_key.digest)))


def test_indexer_is_stateless():
    indexer = PatternIndex()
    evaluator = TrajectoryOutcomeEvaluator()
    trajectory = _trajectory()

    first = indexer.index(trajectory, evaluator)
    second = PatternIndex().index(trajectory, evaluator)

    assert first == second
    assert not vars(indexer)


def test_corrupted_pattern_record_digest_is_rejected():
    record = PatternIndex().index(_trajectory(), TrajectoryOutcomeEvaluator())

    corrupted = record.__class__(
        pattern_key=record.pattern_key,
        event_ids=record.event_ids,
        event_type_sequence=record.event_type_sequence,
        outcome_quality=record.outcome_quality,
        delta_progress=record.delta_progress,
        cost=record.cost,
        causal_efficiency=record.causal_efficiency,
        success=record.success,
        anti_pattern=record.anti_pattern,
        record_digest="corrupted",
    )

    with pytest.raises(CausalConsistencyError, match="digest"):
        PatternIndex().validate_record(corrupted)
