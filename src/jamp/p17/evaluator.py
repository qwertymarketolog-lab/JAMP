"""Deterministic, read-only trajectory and outcome evaluation for P17.1."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import inspect
from types import MappingProxyType
from typing import Any, Mapping

from ..domain.exceptions import NonDeterministicEvaluationError
from ..domain.replay import ReadonlyRegistry


ALPHA = 1.0
BETA = 1.0
GAMMA = 1.0
EPSILON = 1e-12


def _freeze_graph(graph: Mapping[str, tuple[str, ...]]) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({key: tuple(sorted(value)) for key, value in sorted(graph.items())})


def _causal_depth(parents: Mapping[str, tuple[str, ...]]) -> int:
    nodes = set(parents)
    for parent_ids in parents.values():
        nodes.update(parent_ids)
    memo: dict[str, int] = {}

    def depth(node: str, active: frozenset[str] = frozenset()) -> int:
        if node in memo:
            return memo[node]
        if node in active:
            raise ValueError("Causal trajectory contains a cycle.")
        parent_ids = parents.get(node, ())
        value = 1 + max((depth(parent, active | {node}) for parent in parent_ids), default=0)
        memo[node] = value
        return value

    return max((depth(node) for node in sorted(nodes)), default=0)


@dataclass(frozen=True)
class CausalTrajectory:
    """Immutable trajectory projection consumed by the evaluator."""

    registry: ReadonlyRegistry
    delta_progress: float
    outcome_quality: float
    causal_parents: Mapping[str, tuple[str, ...]]
    candidate_graph: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        if not isinstance(self.registry, ReadonlyRegistry):
            raise TypeError("CausalTrajectory requires a ReadonlyRegistry.")
        if self.delta_progress < 0:
            raise ValueError("delta_progress must be non-negative.")
        if not 0 <= self.outcome_quality <= 1:
            raise ValueError("outcome_quality must be in [0, 1].")
        object.__setattr__(self, "causal_parents", _freeze_graph(self.causal_parents))
        object.__setattr__(self, "candidate_graph", _freeze_graph(self.candidate_graph))

    @property
    def causal_depth(self) -> int:
        return _causal_depth(self.causal_parents)

    @property
    def candidate_count(self) -> int:
        nodes = set(self.candidate_graph)
        for children in self.candidate_graph.values():
            nodes.update(children)
        return len(nodes)

    @property
    def branching_burden(self) -> int:
        return sum(len(children) for children in self.candidate_graph.values())


@dataclass(frozen=True)
class EvaluationResult:
    """Immutable P17.1 evaluation result."""

    delta_progress: float
    outcome_quality: float
    causal_depth: int
    candidate_count: int
    branching_burden: int
    cost: float
    causal_efficiency: float


class TrajectoryOutcomeEvaluator:
    """Pure/stateless evaluator with read-only Registry access only."""

    @property
    def evaluator_digest(self) -> str:
        """Stable SHA-256 commitment to this evaluator implementation."""
        source = inspect.getsource(type(self))
        contract = f"{source}\n{ALPHA!r}\n{BETA!r}\n{GAMMA!r}\n{EPSILON!r}"
        return hashlib.sha256(contract.encode("utf-8")).hexdigest()

    def validate_digest(self, expected_digest: str) -> bool:
        """Reject a corrupted or mismatched evaluator digest."""
        if expected_digest != self.evaluator_digest:
            raise ValueError("Evaluator digest mismatch.")
        return True

    def evaluate(
        self,
        trajectory: CausalTrajectory,
        environment_metadata: Mapping[str, Any] | None = None,
    ) -> EvaluationResult:
        """Evaluate a frozen trajectory; environment metadata is deliberately ignored."""
        if not isinstance(trajectory, CausalTrajectory):
            raise TypeError("evaluate() requires a CausalTrajectory.")

        depth = trajectory.causal_depth
        candidate_count = trajectory.candidate_count
        branching_burden = trajectory.branching_burden
        cost = ALPHA * depth + BETA * candidate_count + GAMMA * branching_burden
        efficiency = (trajectory.delta_progress * trajectory.outcome_quality) / (cost + EPSILON)

        return EvaluationResult(
            delta_progress=trajectory.delta_progress,
            outcome_quality=trajectory.outcome_quality,
            causal_depth=depth,
            candidate_count=candidate_count,
            branching_burden=branching_burden,
            cost=cost,
            causal_efficiency=efficiency,
        )

    def assert_deterministic(self, trajectory: CausalTrajectory) -> EvaluationResult:
        """Evaluate twice and reject any non-deterministic result."""
        first = self.evaluate(trajectory)
        second = self.evaluate(trajectory)
        if first != second:
            raise NonDeterministicEvaluationError(
                "Evaluator produced different results for identical input."
            )
        return first

    @staticmethod
    def synthetic_trajectory(
        registry: ReadonlyRegistry,
        depth: int,
        candidate_count: int,
        branching_burden: int,
    ) -> CausalTrajectory:
        """Create deterministic structural fixtures for contract tests."""
        if depth < 1 or candidate_count < 1 or branching_burden < 0:
            raise ValueError("Invalid synthetic trajectory dimensions.")
        if candidate_count < depth:
            raise ValueError("candidate_count must be >= depth.")
        max_edges = candidate_count * (candidate_count - 1) // 2
        if branching_burden > max_edges:
            raise ValueError("branching_burden exceeds the DAG edge bound.")

        nodes = [f"c{i}" for i in range(candidate_count)]
        parents: dict[str, tuple[str, ...]] = {node: () for node in nodes}
        for index in range(1, depth):
            parents[nodes[index]] = (nodes[index - 1],)
        for index in range(depth, candidate_count):
            parents[nodes[index]] = (nodes[depth - 1],)

        candidate_graph: dict[str, list[str]] = {node: [] for node in nodes}
        edges = ((nodes[i], nodes[j]) for i in range(candidate_count) for j in range(i + 1, candidate_count))
        for parent, child in list(edges)[:branching_burden]:
            candidate_graph[parent].append(child)

        return CausalTrajectory(
            registry=registry,
            delta_progress=1.0,
            outcome_quality=1.0,
            causal_parents=parents,
            candidate_graph={key: tuple(value) for key, value in candidate_graph.items()},
        )
