import pytest

from jamp.p18.experiment_registry import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentArtifact,
    ExperimentRegistry,
)


def make_artifact(experiment_id="exp-001"):
    return ExperimentArtifact.create(
        experiment_id=experiment_id,
        problem_id="problem-001",
        task_family="deterministic-demo",
        seed=7,
        experiment_config={"generations": 4, "min_weight": 0.1},
        genesis_state={"state": "GENESIS"},
        policy={"exploit": 0.15, "explore": 0.15},
        event_dag={"events": [{"event_id": "GENESIS", "parents": []}]},
        trajectories=[{"generation": 0, "digest": "traj-0"}],
        pattern_index={"patterns": [{"digest": "pattern-0"}]},
        policy_updates=[{"event_id": "POLICY_0001", "previous": "p0", "new": "p1"}],
        replay_result={"verified": True, "state_digest": "state-0"},
        metrics={"causal_efficiency": 0.25, "cost": 4.0},
    )


def test_artifact_has_canonical_schema_and_valid_digest():
    artifact = make_artifact()
    data = artifact.to_dict()

    assert data["schema_version"] == EXPERIMENT_SCHEMA_VERSION
    assert set(data) == {
        "schema_version", "experiment_id", "problem_id", "task_family", "seed",
        "experiment_config", "genesis_state", "policy", "event_dag", "trajectories",
        "pattern_index", "policy_updates", "replay_result", "metrics", "artifact_digest",
    }
    assert artifact.verify()
    assert artifact.artifact_digest == artifact.to_dict()["artifact_digest"]


def test_artifact_is_deeply_immutable():
    artifact = make_artifact()
    with pytest.raises(TypeError):
        artifact.payload["metrics"] = {"cost": 9}
    with pytest.raises(TypeError):
        artifact.payload["metrics"]["cost"] = 9
    with pytest.raises(TypeError):
        artifact.payload["experiment_config"]["generations"] = 99


def test_round_trip_preserves_canonical_artifact():
    artifact = make_artifact()
    restored = ExperimentArtifact.from_dict(artifact.to_dict())

    assert restored.verify()
    assert restored.to_json() == artifact.to_json()
    assert restored.artifact_digest == artifact.artifact_digest


def test_tampering_is_rejected():
    artifact = make_artifact()
    tampered = artifact.to_dict()
    tampered["metrics"]["cost"] = 999

    with pytest.raises(ValueError, match="digest verification failed"):
        ExperimentArtifact.from_dict(tampered)


def test_registry_is_append_only_and_rejects_duplicate_ids():
    first = make_artifact("exp-001")
    second = make_artifact("exp-002")
    registry = ExperimentRegistry().register(first)

    assert registry.verify()
    assert registry.get("exp-001") == first
    assert len(registry.artifacts) == 1

    expanded = registry.register(second)
    assert len(registry.artifacts) == 1
    assert len(expanded.artifacts) == 2

    with pytest.raises(ValueError, match="already registered"):
        expanded.register(make_artifact("exp-001"))


def test_registry_round_trip_and_invalid_schema_rejection():
    registry = ExperimentRegistry().register(make_artifact())
    restored = ExperimentRegistry.from_dict(registry.to_dict())

    assert restored.verify()
    assert restored.to_json() == registry.to_json()

    invalid = registry.to_dict()
    invalid["schema_version"] = "999"
    with pytest.raises(ValueError, match="unsupported"):
        ExperimentRegistry.from_dict(invalid)
