"""Deterministic autonomous closed-loop experiment harness for P17.6."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from ..domain.event import canonical_json, sha256_text
from ..domain.replay import ReadonlyRegistry
from ..events.dag import EventDAG
from .dynamic_policy import DynamicPolicyAdaptor, PolicyWeights
from .evaluator import CausalTrajectory, TrajectoryOutcomeEvaluator
from .pattern_index import PatternIndex, PatternRecord
from .policy_event import PolicyUpdateEvent
from .policy_guided_search import PolicyGuidedSearch
from .policy_replay import PolicyReplayEngine

_DEFAULT_POLICY = PolicyWeights.from_mapping({"exploit": 0.1, "explore": 0.1}, total_budget=0.2, min_weight=0.1)
_EXPERIMENT_BUDGET = 0.3


@dataclass(frozen=True)
class ExperimentIteration:
    generation: int
    policy: PolicyWeights
    policy_digest: str
    trajectory_digest: str
    causal_efficiency: float
    cost: float
    branching_burden: int
    pattern_digest: str
    evidence_source: str
    replay_policy_digest: str
    policy_event_id: str


@dataclass(frozen=True)
class ExperimentResult:
    iterations: tuple[ExperimentIteration, ...]
    causal_chain: tuple[Mapping[str, str | tuple[str, ...]], ...] = ()
    replay_verified: bool = True

    @property
    def delta_causal_efficiency(self) -> float:
        if len(self.iterations) < 2:
            return 0.0
        return self.iterations[-1].causal_efficiency - self.iterations[0].causal_efficiency

    def to_artifact(self, *, experiment_id: str, problem_id: str, task_family: str, seed: int,
                    experiment_config: Mapping[str, Any] | None = None):
        """Pure P18 projection; P17.6 execution state is not recomputed."""
        from ..p18.experiment_registry import ExperimentArtifact
        return ExperimentArtifact.from_experiment_result(
            self, experiment_id=experiment_id, problem_id=problem_id,
            task_family=task_family, seed=seed, experiment_config=experiment_config,
        )

    def report(self) -> dict[str, object]:
        from .experiment_report import build_report
        return build_report(self)

    def report_json(self) -> str:
        from .experiment_report import serialize_report
        return serialize_report(self.report())

    def report_cli(self) -> str:
        from .experiment_report import render_cli
        return render_cli(self.report())


@dataclass(frozen=True, slots=True)
class ClosedLoopExperiment:
    """Pure orchestration of search, evaluation, indexing, adaptation and replay."""
    generations: int = 3
    initial_policy: PolicyWeights = field(default=_DEFAULT_POLICY)
    genesis_id: str = "GENESIS"
    evaluator: TrajectoryOutcomeEvaluator = field(default_factory=TrajectoryOutcomeEvaluator)
    pattern_index: PatternIndex = field(default_factory=PatternIndex)
    search: PolicyGuidedSearch = field(default_factory=PolicyGuidedSearch)

    def __post_init__(self) -> None:
        if self.generations < 1:
            raise ValueError("generations must be >= 1")
        if not isinstance(self.initial_policy, PolicyWeights):
            raise TypeError("initial_policy must be PolicyWeights")
        if not self.genesis_id:
            raise ValueError("genesis_id must be non-empty")

    def run(self, genesis_id: str | None = None, initial_policy: PolicyWeights | None = None, *, generations: int | None = None) -> ExperimentResult:
        gid = self.genesis_id if genesis_id is None else genesis_id
        policy = self.initial_policy if initial_policy is None else initial_policy
        count = self.generations if generations is None else generations
        if count < 1:
            raise ValueError("generations must be >= 1")
        if not isinstance(policy, PolicyWeights):
            raise TypeError("initial_policy must be PolicyWeights")
        dag = EventDAG()
        replay = PolicyReplayEngine()
        records: list[ExperimentIteration] = []
        causal_chain: list[Mapping[str, str | tuple[str, ...]]] = []
        replay_verified = True
        for generation in range(count):
            search_result = self.search.run(gid, policy)
            trajectory = self._trajectory(policy)
            evaluation = self.evaluator.assert_deterministic(trajectory)
            pattern = self.pattern_index.index(trajectory, self.evaluator)
            replay_result = replay.replay(dag, genesis_state=self.initial_policy)
            replay_verified = replay_verified and replay_result.state == policy
            records.append(ExperimentIteration(generation, policy, search_result.policy_digest, search_result.trajectory_digest, evaluation.causal_efficiency, evaluation.cost, evaluation.branching_burden, pattern.record_digest, "pattern_index" if generation else "baseline", replay_result.state_digest, f"POLICY_{generation:04d}" if generation else EventDAG.GENESIS_ID))
            if generation + 1 < count:
                evidence = self._pattern_evidence(policy, pattern)
                next_budget = max(policy.total_budget, _EXPERIMENT_BUDGET)
                scale = next_budget / policy.total_budget
                expanded_values = {name: value * scale for name, value in policy.values}
                adaptation_policy = PolicyWeights.from_mapping(expanded_values, total_budget=next_budget, min_weight=policy.min_weight)
                new_policy = PolicyWeights.from_mapping(DynamicPolicyAdaptor(adaptation_policy).update(evidence), total_budget=next_budget, min_weight=policy.min_weight)
                event = PolicyUpdateEvent.create(event_id=f"POLICY_{generation + 1:04d}", parent_ids=tuple(sorted(dag.head_ids)), previous_state=policy, new_state=new_policy, evidence_digest=sha256_text(canonical_json(dict(sorted(evidence.items())))), causal_source="pattern_index", dag=dag)
                dag.nodes[event.event_id] = event
                dag.head_ids = [event.event_id]
                causal_chain.append(MappingProxyType({"event_id": event.event_id, "parent_id": event.parent_ids[0] if len(event.parent_ids) == 1 else event.parent_ids, "previous_policy_digest": event.previous_state_digest, "new_policy_digest": event.new_state_digest, "evidence_digest": event.evidence_digest, "policy_update_digest": event.policy_update_digest}))
                policy = new_policy
        return ExperimentResult(tuple(records), tuple(causal_chain), replay_verified)

    def _trajectory(self, policy: PolicyWeights) -> CausalTrajectory:
        weights = dict(policy.values)
        ordered = sorted(weights)
        exploit = weights.get("exploit", weights[ordered[0]])
        explore = weights.get("explore", weights[ordered[-1]])
        branching = 1 if exploit <= explore + 1e-12 else 0
        return CausalTrajectory(registry=_empty_readonly_registry(), delta_progress=1.0, outcome_quality=1.0, causal_parents={"c0": (), "c1": ("c0",)}, candidate_graph={"c0": ("c1",) if branching else (), "c1": ()})

    @staticmethod
    def _pattern_evidence(policy: PolicyWeights, pattern: PatternRecord) -> Mapping[str, float]:
        weights = dict(policy.values)
        ce = max(pattern.causal_efficiency, 0.0)
        advantage = 1.0 / (1.0 + pattern.cost)
        total = max(policy.total_budget, 1e-12)
        evidence: dict[str, float] = {}
        for name in sorted(weights):
            normalized_weight = weights[name] / total
            if name == "exploit":
                evidence[name] = ce * (1.0 + advantage) * (1.0 + normalized_weight)
            elif name == "explore":
                evidence[name] = ce * (1.0 + 0.5 * advantage) * (1.0 + normalized_weight)
            else:
                evidence[name] = ce * (1.0 + normalized_weight)
        return MappingProxyType(evidence)


def _empty_readonly_registry() -> ReadonlyRegistry:
    return ReadonlyRegistry(())


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a canonical P17.6 closed-loop experiment report.")
    parser.add_argument("--export-report", metavar="FILE", required=True, help="run the experiment and write the sealed canonical JSON report")
    parser.add_argument("--generations", type=int, default=3, help="number of generations to execute (default: 3)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_cli_parser().parse_args(argv)
    from .experiment_report import write_report
    result = ClosedLoopExperiment(generations=args.generations).run()
    destination = write_report(result.report(), args.export_report)
    print(result.report_cli())
    print(f"Artifact: {destination}")
    return 0


ClosedLoopExperimentResult = ExperimentResult


if __name__ == "__main__":
    raise SystemExit(main())
