import json

import pytest

from jamp.p17.closed_loop import ClosedLoopExperiment, ExperimentResult
from jamp.p18.experiment_registry import ExperimentArtifact, ExperimentRegistry


def test_experiment_result_to_artifact_preserves_three_verification_layers():
    result = ClosedLoopExperiment(generations=4).run()
    artifact = result.to_artifact(
        experiment_id="p17-6-live-001",
        problem_id="deterministic-demo-001",
        task_family="deterministic-demo",
        seed=0,
        experiment_config={"source": "p17.6"},
    )

    assert isinstance(result, ExperimentResult)
    assert artifact.verify()
    data = artifact.to_dict()

    # Level A: metrics are projected directly from each iteration.
    assert data["metrics"]["baseline_causal_efficiency"] == result.iterations[0].causal_efficiency
    assert data["metrics"]["final_causal_efficiency"] == result.iterations[-1].causal_efficiency
    assert data["metrics"]["delta_causal_efficiency"] == result.delta_causal_efficiency

    # Level B: immutable causal policy-update chain is retained verbatim.
    assert data["policy_updates"] == [dict(event) for event in result.causal_chain]
    assert data["event_dag"]["events"] == data["policy_updates"]

    # Level C: replay state/digest evidence is retained for every generation.
    assert data["replay_result"]["verified"] is result.replay_verified
    assert len(data["replay_result"]["states"]) == len(result.iterations)
    assert all(state["verified"] for state in data["replay_result"]["states"])


def test_artifact_round_trip_is_byte_canonical_and_digest_stable():
    result = ClosedLoopExperiment(generations=4).run()
    artifact = result.to_artifact(
        experiment_id="round-trip",
        problem_id="problem-001",
        task_family="family-a",
        seed=11,
    )
    restored = ExperimentArtifact.from_dict(json.loads(artifact.to_json()))

    assert restored.verify()
    assert restored.artifact_digest == artifact.artifact_digest
    assert restored.to_json() == artifact.to_json()


def test_registry_ingests_live_result_in_one_step_and_remains_append_only():
    result = ClosedLoopExperiment(generations=2).run()
    registry = ExperimentRegistry()
    expanded = registry.register_result(
        result,
        experiment_id="live-001",
        problem_id="problem-001",
        task_family="family-a",
        seed=7,
    )

    assert len(registry.artifacts) == 0
    assert len(expanded.artifacts) == 1
    assert expanded.verify()
    assert expanded.get("live-001").artifact_digest

    with pytest.raises(ValueError, match="already registered"):
        expanded.register_result(
            result,
            experiment_id="live-001",
            problem_id="problem-001",
            task_family="family-a",
            seed=7,
        )


def test_bridge_rejects_empty_result_and_invalid_runtime_type():
    with pytest.raises(ValueError, match="at least one iteration"):
        ExperimentArtifact.from_experiment_result(
            ExperimentResult(()),
            experiment_id="empty",
            problem_id="problem",
            task_family="family",
            seed=1,
        )

    with pytest.raises(TypeError, match="ExperimentResult"):
        ExperimentArtifact.from_experiment_result(
            object(),
            experiment_id="bad",
            problem_id="problem",
            task_family="family",
            seed=1,
        )
