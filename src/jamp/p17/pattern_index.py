"""Deterministic, immutable Cross-Session Pattern Index for P17.2."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Iterable

from ..domain.event import canonical_json
from ..domain.exceptions import CausalConsistencyError
from ..domain.replay import ReadonlyRegistry
from .evaluator import CausalTrajectory, TrajectoryOutcomeEvaluator


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _registry_digest(registry: ReadonlyRegistry) -> str:
    return _digest([
        {"record_id": r.record_id, "kind": r.kind, "payload": r.payload}
        for r in registry.all()
    ])


def _causal_material(trajectory: CausalTrajectory) -> list[dict[str, object]]:
    return [
        {"node": node, "parents": tuple(sorted(trajectory.causal_parents[node]))}
        for node in sorted(trajectory.causal_parents)
    ]


@dataclass(frozen=True)
class PatternKey:
    """Canonical identity of a state reached through a causal structure."""

    state_digest: str
    causal_sequence_digest: str
    causal_depth: int
    branching_signature: tuple[tuple[str, int], ...]
    evaluator_digest: str

    @property
    def digest(self) -> str:
        return _digest({
            "state_digest": self.state_digest,
            "causal_sequence_digest": self.causal_sequence_digest,
            "causal_depth": self.causal_depth,
            "branching_signature": self.branching_signature,
            "evaluator_digest": self.evaluator_digest,
        })


@dataclass(frozen=True)
class PatternRecord:
    """Immutable indexed experience record."""

    pattern_key: PatternKey
    event_ids: tuple[str, ...]
    event_type_sequence: tuple[str, ...]
    outcome_quality: float
    delta_progress: float
    cost: float
    causal_efficiency: float
    success: bool
    anti_pattern: bool
    record_digest: str


class PatternIndex:
    """Pure/stateless producer of immutable cross-session pattern records."""

    def index(
        self,
        trajectory: CausalTrajectory,
        evaluator: TrajectoryOutcomeEvaluator,
        evaluator_digest: str | None = None,
    ) -> PatternRecord:
        if not isinstance(trajectory, CausalTrajectory):
            raise TypeError("index() requires a CausalTrajectory.")
        if not isinstance(evaluator, TrajectoryOutcomeEvaluator):
            raise TypeError("index() requires a TrajectoryOutcomeEvaluator.")

        bound_digest = evaluator.evaluator_digest
        if evaluator_digest is not None and evaluator_digest != bound_digest:
            raise ValueError("Evaluator digest mismatch.")

        result = evaluator.assert_deterministic(trajectory)
        causal_material = _causal_material(trajectory)
        key = PatternKey(
            state_digest=_registry_digest(trajectory.registry),
            causal_sequence_digest=_digest(causal_material),
            causal_depth=result.causal_depth,
            branching_signature=tuple(
                (node, len(children))
                for node, children in sorted(trajectory.candidate_graph.items())
            ),
            evaluator_digest=bound_digest,
        )

        # P17.1 does not yet expose EventNode types in CausalTrajectory. The
        # canonical structural node sequence is therefore retained as the
        # deterministic event/path projection until the EventDAG adapter lands.
        event_ids = tuple(sorted(trajectory.causal_parents))
        event_type_sequence = tuple("causal_node" for _ in event_ids)
        success = result.outcome_quality > 0.0 and result.delta_progress > 0.0
        anti_pattern = not success

        material = {
            "pattern_key": key.digest,
            "event_ids": event_ids,
            "event_type_sequence": event_type_sequence,
            "outcome_quality": result.outcome_quality,
            "delta_progress": result.delta_progress,
            "cost": result.cost,
            "causal_efficiency": result.causal_efficiency,
            "success": success,
            "anti_pattern": anti_pattern,
        }
        record_digest = _digest(material)
        return PatternRecord(
            pattern_key=key,
            event_ids=event_ids,
            event_type_sequence=event_type_sequence,
            outcome_quality=result.outcome_quality,
            delta_progress=result.delta_progress,
            cost=result.cost,
            causal_efficiency=result.causal_efficiency,
            success=success,
            anti_pattern=anti_pattern,
            record_digest=record_digest,
        )

    @staticmethod
    def rank(records: Iterable[PatternRecord]) -> tuple[PatternRecord, ...]:
        return tuple(sorted(records, key=lambda r: (-r.causal_efficiency, r.pattern_key.digest)))

    @staticmethod
    def validate_record(record: PatternRecord) -> bool:
        material = {
            "pattern_key": record.pattern_key.digest,
            "event_ids": record.event_ids,
            "event_type_sequence": record.event_type_sequence,
            "outcome_quality": record.outcome_quality,
            "delta_progress": record.delta_progress,
            "cost": record.cost,
            "causal_efficiency": record.causal_efficiency,
            "success": record.success,
            "anti_pattern": record.anti_pattern,
        }
        expected = _digest(material)
        if record.record_digest != expected:
            raise CausalConsistencyError("Pattern record digest mismatch.")
        return True

    @staticmethod
    def freeze_mapping(value: dict[str, object]) -> MappingProxyType:
        """Expose a deterministic immutable mapping utility for future adapters."""
        return MappingProxyType(dict(sorted(value.items())))
