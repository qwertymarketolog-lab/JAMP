from research.exp21.phase3_contract import validate_artifact, validate_observation


def _observation():
    return {
        "experiment_id": "EXP-21-PHASE3-TOPOLOGY-V1",
        "phase": 3,
        "target_commit": "abc",
        "workload_spec_id": "EXP-21-PHASE0-G4-CANONICAL-V1",
        "workload_definition_hash": (
            "f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92"
        ),
        "experiment_seed": 2103,
        "pair_id": "001",
        "condition": "CONTROL",
        "timestamp": "2026-09-23T00:00:00+00:00",
        "runner_name": "test",
        "runner_os": "Linux",
        "runner_arch": "x86_64",
        "kernel": "test",
        "python_version": "3.14",
        "cpu_count_visible": 2,
        "cpu_affinity_before": [0, 1],
        "cpu_affinity_after": [0],
        "placement_before": {
            "package": "0",
            "core": "0",
            "thread": 0,
            "sibling": [0, 1],
        },
        "placement_after": {
            "package": "0",
            "core": "0",
            "thread": 0,
            "sibling": [0, 1],
        },
        "topology_package": "0",
        "topology_core": "0",
        "topology_thread": 0,
        "topology_sibling": [0, 1],
        "topology_verified": True,
        "affinity_verified": True,
        "wall_ms": 10.0,
        "cpu_ms": 9.0,
        "non_cpu_delta_ms": 1.0,
        "gc_enabled": True,
        "gc_gen2_collections": 0,
    }


def test_observation_accepts_verified_topology():
    assert validate_observation(_observation(), expected_target_commit="abc") == []


def test_observation_rejects_unverified_topology():
    item = _observation()
    item["topology_verified"] = False
    assert "topology_not_verified" in validate_observation(
        item, expected_target_commit="abc"
    )


def test_artifact_requires_thirty_pairs():
    artifact = {
        "observations": [],
        "n_pairs": 0,
        "wilcoxon_p": 1.0,
        "alpha": 0.01,
        "median_delta_ms": 0.0,
        "status": "INCONCLUSIVE",
    }
    valid, errors = validate_artifact(artifact, expected_target_commit="abc")
    assert not valid
    assert "valid_pair_count=0;required=30" in errors
