"""Immutable, canonical experiment artifacts for P18.1."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from ..p17.closed_loop import ExperimentResult

EXPERIMENT_SCHEMA_VERSION = "1.0"
_DIGEST_FIELD = "artifact_digest"
_REQUIRED_FIELDS = (
    "experiment_id", "problem_id", "task_family", "seed", "experiment_config",
    "genesis_state", "policy", "event_dag", "trajectories", "pattern_index",
    "policy_updates", "replay_result", "metrics",
)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported artifact value type: {type(value).__name__}")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(_thaw(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _unsigned_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = _thaw(payload)
    unsigned[_DIGEST_FIELD] = None
    return unsigned


def compute_artifact_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(_unsigned_payload(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ExperimentArtifact:
    """One complete, immutable and cryptographically sealed experiment run."""

    payload: Mapping[str, Any]

    @classmethod
    def create(cls, *, experiment_id: str, problem_id: str, task_family: str, seed: int,
               experiment_config: Mapping[str, Any], genesis_state: Mapping[str, Any],
               policy: Mapping[str, Any], event_dag: Mapping[str, Any], trajectories: Any,
               pattern_index: Any, policy_updates: Any, replay_result: Mapping[str, Any],
               metrics: Mapping[str, Any]) -> "ExperimentArtifact":
        if not experiment_id or not problem_id or not task_family:
            raise ValueError("experiment_id, problem_id and task_family must be non-empty")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError("seed must be an integer")
        payload = {
            "schema_version": EXPERIMENT_SCHEMA_VERSION, "experiment_id": experiment_id,
            "problem_id": problem_id, "task_family": task_family, "seed": seed,
            "experiment_config": experiment_config, "genesis_state": genesis_state,
            "policy": policy, "event_dag": event_dag, "trajectories": trajectories,
            "pattern_index": pattern_index, "policy_updates": policy_updates,
            "replay_result": replay_result, "metrics": metrics, _DIGEST_FIELD: None,
        }
        frozen = _freeze(payload)
        sealed = dict(_thaw(frozen))
        sealed[_DIGEST_FIELD] = compute_artifact_digest(frozen)
        return cls(_freeze(sealed))

    @classmethod
    def from_experiment_result(cls, result: "ExperimentResult", *, experiment_id: str,
                               problem_id: str, task_family: str, seed: int,
                               experiment_config: Mapping[str, Any] | None = None) -> "ExperimentArtifact":
        """Pure projection of a P17.6 result; no metrics or decisions are recomputed."""
        if not isinstance(result, _experiment_result_type()):
            raise TypeError("result must be an ExperimentResult")
        if not result.iterations:
            raise ValueError("experiment result must contain at least one iteration")
        it = result.iterations
        trajectories = [{"generation": x.generation, "policy_digest": x.policy_digest,
                         "trajectory_digest": x.trajectory_digest, "causal_efficiency": x.causal_efficiency,
                         "cost": x.cost, "branching_burden": x.branching_burden,
                         "pattern_digest": x.pattern_digest, "evidence_source": x.evidence_source} for x in it]
        policies = [{"generation": x.generation, "policy_digest": x.policy_digest,
                     "weights": list(x.policy.values), "total_budget": x.policy.total_budget,
                     "min_weight": x.policy.min_weight} for x in it]
        pattern_records = [{"generation": x.generation, "pattern_digest": x.pattern_digest} for x in it]
        replay_states = [{"generation": x.generation, "verified": x.replay_policy_digest == x.policy_digest,
                          "state_digest": x.replay_policy_digest, "policy_digest": x.policy_digest} for x in it]
        metrics = {
            "baseline_causal_efficiency": it[0].causal_efficiency,
            "final_causal_efficiency": it[-1].causal_efficiency,
            "delta_causal_efficiency": result.delta_causal_efficiency,
            "iterations": [{"generation": x.generation, "causal_efficiency": x.causal_efficiency,
                             "cost": x.cost, "branching_burden": x.branching_burden} for x in it],
            "replay_verified": result.replay_verified,
            "trajectory_divergence": len({x.trajectory_digest for x in it}) == len(it),
            "exploration_floor_preserved": all(w >= x.policy.min_weight for x in it for _, w in x.policy.values),
        }
        chain = [dict(x) for x in result.causal_chain]
        genesis = it[0].policy
        config = {"generations": len(it), "initial_policy_budget": genesis.total_budget,
                  "min_weight": genesis.min_weight}
        if experiment_config:
            config.update(experiment_config)
        return cls.create(
            experiment_id=experiment_id, problem_id=problem_id, task_family=task_family, seed=seed,
            experiment_config=config,
            genesis_state={"genesis_id": "GENESIS", "policy_digest": it[0].policy_digest,
                           "policy_weights": list(genesis.values)},
            policy={"generations": policies},
            event_dag={"genesis_id": "GENESIS", "events": chain},
            trajectories=trajectories,
            pattern_index={"records": pattern_records},
            policy_updates=chain,
            replay_result={"verified": result.replay_verified, "states": replay_states},
            metrics=metrics,
        )

    @property
    def experiment_id(self) -> str:
        return self.payload["experiment_id"]

    @property
    def artifact_digest(self) -> str:
        return self.payload[_DIGEST_FIELD]

    def verify(self) -> bool:
        digest = self.payload.get(_DIGEST_FIELD)
        return isinstance(digest, str) and digest == compute_artifact_digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self.payload)

    def to_json(self) -> str:
        if not self.verify():
            raise ValueError("experiment artifact digest verification failed")
        return canonical_json(self.payload)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExperimentArtifact":
        missing = [field for field in _REQUIRED_FIELDS if field not in payload]
        if missing:
            raise ValueError(f"missing required artifact fields: {', '.join(missing)}")
        if payload.get("schema_version") != EXPERIMENT_SCHEMA_VERSION:
            raise ValueError("unsupported experiment artifact schema version")
        artifact = cls(_freeze(payload))
        if not artifact.verify():
            raise ValueError("experiment artifact digest verification failed")
        return artifact


@dataclass(frozen=True, slots=True)
class ExperimentRegistry:
    """Append-only registry represented entirely by immutable artifacts."""
    artifacts: tuple[ExperimentArtifact, ...] = ()

    def register(self, artifact: ExperimentArtifact) -> "ExperimentRegistry":
        if not isinstance(artifact, ExperimentArtifact):
            raise TypeError("registry accepts only ExperimentArtifact")
        if not artifact.verify():
            raise ValueError("cannot register an artifact with an invalid digest")
        if any(existing.experiment_id == artifact.experiment_id for existing in self.artifacts):
            raise ValueError(f"experiment_id already registered: {artifact.experiment_id}")
        return ExperimentRegistry(self.artifacts + (artifact,))

    def register_result(self, result: "ExperimentResult", *, experiment_id: str,
                        problem_id: str, task_family: str, seed: int,
                        experiment_config: Mapping[str, Any] | None = None) -> "ExperimentRegistry":
        return self.register(ExperimentArtifact.from_experiment_result(
            result, experiment_id=experiment_id, problem_id=problem_id,
            task_family=task_family, seed=seed, experiment_config=experiment_config))

    def get(self, experiment_id: str) -> ExperimentArtifact:
        for artifact in self.artifacts:
            if artifact.experiment_id == experiment_id:
                return artifact
        raise KeyError(experiment_id)

    def verify(self) -> bool:
        ids = [a.experiment_id for a in self.artifacts]
        return len(ids) == len(set(ids)) and all(a.verify() for a in self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": EXPERIMENT_SCHEMA_VERSION,
                "artifacts": [a.to_dict() for a in self.artifacts]}

    def to_json(self) -> str:
        if not self.verify():
            raise ValueError("experiment registry contains an invalid artifact")
        return canonical_json(_freeze(self.to_dict()))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExperimentRegistry":
        if payload.get("schema_version") != EXPERIMENT_SCHEMA_VERSION:
            raise ValueError("unsupported experiment registry schema version")
        registry = cls(tuple(ExperimentArtifact.from_dict(x) for x in payload.get("artifacts", ())))
        if not registry.verify():
            raise ValueError("experiment registry integrity verification failed")
        return registry


def _experiment_result_type() -> type:
    from ..p17.closed_loop import ExperimentResult
    return ExperimentResult
