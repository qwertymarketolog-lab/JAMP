"""P18.3 RED gate: controlled cross-task pattern transfer."""

from copy import deepcopy
from hashlib import sha256

import pytest

from jamp.p18.experiment_registry import ExperimentArtifact, ExperimentRegistry
from jamp.p18.task_family_isolation import TaskFamilyBoundary

FAMILY_A = "family-A"
FAMILY_B = "family-B"
FAMILY_C = "family-C"


def _digest(payload):
    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _source_pattern():
    return {
        "pattern_id": "PATTERN-A-001",
        "family_id": FAMILY_A,
        "task_id": "task-a",
        "payload": {"rule": "observed-structure", "value": 42},
        "provenance": {"experiment_id": "EXP-A-001", "generation": 3},
    }


def _authorization(source_pattern, source_family=FAMILY_A, target_family=FAMILY_B):
    return {
        "authorization_id": "AUTH-A-B-001",
        "source_family": source_family,
        "target_family": target_family,
        "source_digest": _digest(source_pattern),
        "provenance": {"actor": "jamp-test", "reason": "controlled-transfer-test"},
        "policy_reason": "explicit-cross-task-transfer",
    }


def _projection(source_pattern, authorization):
    return {
        "pattern_id": "PATTERN-B-001",
        "family_id": authorization["target_family"],
        "task_id": "task-b",
        "payload": deepcopy(source_pattern["payload"]),
        "provenance": {
            "transferred_from": source_pattern["pattern_id"],
            "source_family": authorization["source_family"],
            "source_digest": authorization["source_digest"],
            "authorization_id": authorization["authorization_id"],
        },
    }


def transfer_gateway():
    try:
        from jamp.p18.controlled_transfer import ControlledTransfer
    except ImportError:
        pytest.fail("P18.3 controlled transfer gateway is not implemented yet")
    return ControlledTransfer


def test_p18_3_t1_transfer_without_authorization_rejected():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    with pytest.raises((ValueError, PermissionError, TypeError)):
        gateway.transfer(source_pattern=source, authorization=None, projection=_projection(source, _authorization(source)))


def test_p18_3_t2_authorization_cannot_be_reused_for_different_target():
    gateway = transfer_gateway()(FAMILY_C)
    source = _source_pattern()
    authorization = _authorization(source, FAMILY_A, FAMILY_B)
    projection = _projection(source, authorization)
    with pytest.raises((ValueError, PermissionError)):
        gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)


def test_p18_3_t3_source_digest_tampering_rejected():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    authorization = _authorization(source)
    authorization["source_digest"] = "0" * 64
    projection = _projection(source, authorization)
    with pytest.raises((ValueError, PermissionError)):
        gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)


def test_p18_3_t4_target_family_spoofing_rejected():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    authorization = _authorization(source)
    projection = _projection(source, authorization)
    projection["family_id"] = FAMILY_C
    with pytest.raises((ValueError, PermissionError)):
        gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)


def test_p18_3_t5_projection_modification_causes_digest_mismatch():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    authorization = _authorization(source)
    projection = _projection(source, authorization)
    result = gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)
    tampered = deepcopy(result)
    tampered["payload"]["value"] = 43
    verify = getattr(gateway, "verify_transfer", None)
    if verify is None:
        pytest.fail("P18.3 transfer gateway must expose verify_transfer for projection integrity")
    assert verify(tampered) is False


def test_p18_3_t6_projection_has_no_shared_source_reference():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    authorization = _authorization(source)
    projection = _projection(source, authorization)
    result = gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)
    assert result is not source
    assert result["family_id"] == FAMILY_B
    assert result["payload"] is not source["payload"]
    assert result["provenance"].get("source_ref") is None


def test_p18_3_t7_identical_inputs_produce_identical_projection_digest():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    authorization = _authorization(source)
    projection = _projection(source, authorization)
    first = gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)
    second = gateway.transfer(
        source_pattern=deepcopy(source),
        authorization=deepcopy(authorization),
        projection=deepcopy(projection),
    )
    digest = getattr(gateway, "projection_digest", None)
    if digest is None:
        pytest.fail("P18.3 transfer gateway must expose projection_digest for deterministic verification")
    assert digest(first) == digest(second)


def test_p18_3_t8_tampered_transfer_replay_rejected():
    gateway = transfer_gateway()(FAMILY_B)
    source = _source_pattern()
    authorization = _authorization(source)
    projection = _projection(source, authorization)
    record = gateway.transfer(source_pattern=source, authorization=authorization, projection=projection)
    replay = deepcopy(record)
    replay["authorization_id"] = "AUTH-TAMPERED"
    replay_fn = getattr(gateway, "replay", None)
    if replay_fn is None:
        pytest.fail("P18.3 transfer gateway must expose replay for audit verification")
    with pytest.raises((ValueError, PermissionError)):
        replay_fn(replay)


def test_p18_3_boundary_integrity_direct_registry_injection_remains_blocked():
    boundary = TaskFamilyBoundary(FAMILY_B)
    foreign = _source_pattern()
    with pytest.raises((ValueError, PermissionError, TypeError)):
        boundary.accept_pattern(foreign)

    registry = ExperimentRegistry()
    artifact = ExperimentArtifact.create(
        experiment_id="EXP-A-001",
        problem_id="problem-a",
        task_family=FAMILY_A,
        seed=1,
        experiment_config={},
        genesis_state={},
        policy={},
        event_dag={},
        trajectories=[],
        pattern_index={},
        policy_updates=[],
        replay_result={},
        metrics={},
    )
    registry = registry.register(artifact)
    with pytest.raises((ValueError, PermissionError, KeyError, TypeError)):
        boundary.lookup_artifact(registry, artifact.experiment_id)
