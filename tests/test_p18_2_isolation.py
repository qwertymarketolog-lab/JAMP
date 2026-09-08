"""P18.2 RED adversarial suite: Zero-Transfer Default across task families."""

import pytest

from jamp.p18.experiment_registry import ExperimentArtifact, ExperimentRegistry


FAMILY_A = "family-a"
FAMILY_B = "family-b"


def make_artifact(*, experiment_id="exp-a", task_family=FAMILY_A):
    return ExperimentArtifact.create(
        experiment_id=experiment_id,
        problem_id="problem-001",
        task_family=task_family,
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


def isolation_boundary():
    """Load the P18.2 boundary contract; absence is an intentional RED state."""
    try:
        from jamp.p18.task_family_isolation import TaskFamilyBoundary
    except ImportError:
        pytest.fail("P18.2 isolation boundary is not implemented yet")
    return TaskFamilyBoundary


def test_policy_update_event_cannot_cross_family_boundary():
    Boundary = isolation_boundary()
    event = {"event_id": "POLICY_A", "task_family": FAMILY_A}
    boundary = Boundary(FAMILY_B)

    with pytest.raises(Exception, match="isolation|family|transfer"):
        boundary.accept_policy_update(event)


def test_pattern_index_cannot_cross_family_boundary():
    Boundary = isolation_boundary()
    pattern = {"pattern_digest": "pattern-a", "task_family": FAMILY_A}
    boundary = Boundary(FAMILY_B)

    with pytest.raises(Exception, match="isolation|family|transfer"):
        boundary.accept_pattern(pattern)


def test_registry_lookup_cannot_cross_family_boundary():
    Boundary = isolation_boundary()
    registry = ExperimentRegistry().register(make_artifact(task_family=FAMILY_A))
    boundary = Boundary(FAMILY_B)

    with pytest.raises((KeyError, ValueError), match="family|isolation|not found"):
        boundary.lookup_artifact(registry, "exp-a")


def test_metadata_spoofing_invalidates_family_bound_digest():
    Boundary = isolation_boundary()
    artifact = make_artifact(task_family=FAMILY_A)
    boundary = Boundary(FAMILY_B)

    with pytest.raises((ValueError, Exception), match="digest|family|isolation"):
        boundary.accept_artifact(artifact)


def test_replay_lineage_from_family_a_is_rejected_by_family_b():
    Boundary = isolation_boundary()
    replay = {"task_family": FAMILY_A, "event_dag": {"genesis_id": "A"}}
    boundary = Boundary(FAMILY_B)

    with pytest.raises(Exception, match="isolation|family|lineage|replay"):
        boundary.accept_replay(replay)


def test_family_identity_is_cryptographically_bound():
    Boundary = isolation_boundary()
    artifact = make_artifact(task_family=FAMILY_A)
    payload = artifact.to_dict()
    payload["task_family"] = FAMILY_B
    boundary = Boundary(FAMILY_B)

    with pytest.raises(Exception, match="digest|family|isolation"):
        boundary.accept_artifact_payload(payload)


def test_shared_reference_cannot_mutate_or_expose_foreign_family_state():
    Boundary = isolation_boundary()
    foreign = {"task_family": FAMILY_A, "state": {"value": 1}}
    boundary = Boundary(FAMILY_B)

    with pytest.raises(Exception, match="isolation|family|reference|transfer"):
        boundary.accept_shared_reference(foreign)


def test_zero_transfer_default_rejects_all_foreign_family_evidence():
    Boundary = isolation_boundary()
    boundary = Boundary(FAMILY_B)
    foreign_evidence = {
        "task_family": FAMILY_A,
        "policy_updates": [{"event_id": "POLICY_A"}],
        "patterns": [{"digest": "pattern-a"}],
        "replay": {"genesis_id": "A"},
    }

    with pytest.raises(Exception, match="isolation|family|transfer"):
        boundary.accept_evidence(foreign_evidence)
