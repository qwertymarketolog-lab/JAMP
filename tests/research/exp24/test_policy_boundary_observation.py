"""Research vectors for EXP-24 policy/tool boundary provenance."""

from __future__ import annotations

from copy import deepcopy

from tests.research.exp24.policy_boundary_observation import (
    build_policy_boundary_observation,
)

BASE_RECORD = {
    "source_ref": "fixture:ai:001",
    "attempt_index": 0,
    "policy": {
        "policy_id": "policy-a",
        "policy_version": "v1",
        "allowed_tools": ["search", "calculator"],
        "permissions": {
            "search": "read",
            "calculator": "execute",
        },
    },
    "provenance": {"run_id": "run-001", "parent_ref": "obs-000"},
}


def test_alternate_policy_changes_identity() -> None:
    baseline = build_policy_boundary_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["policy"]["policy_id"] = "policy-b"
    assert build_policy_boundary_observation(changed).immutable_hash != baseline.immutable_hash


def test_alternate_tool_surface_changes_identity() -> None:
    baseline = build_policy_boundary_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["policy"]["allowed_tools"] = ["search"]
    assert build_policy_boundary_observation(changed).immutable_hash != baseline.immutable_hash


def test_policy_version_change_changes_identity() -> None:
    baseline = build_policy_boundary_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["policy"]["policy_version"] = "v2"
    assert build_policy_boundary_observation(changed).immutable_hash != baseline.immutable_hash


def test_permission_shift_changes_identity() -> None:
    baseline = build_policy_boundary_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["policy"]["permissions"]["calculator"] = "read"
    assert build_policy_boundary_observation(changed).immutable_hash != baseline.immutable_hash


def test_policy_ordering_is_canonical() -> None:
    first = build_policy_boundary_observation(BASE_RECORD)
    changed = deepcopy(BASE_RECORD)
    changed["policy"]["allowed_tools"] = ["calculator", "search"]
    changed["policy"]["permissions"] = {
        "calculator": "execute",
        "search": "read",
    }
    assert build_policy_boundary_observation(changed) == first


def test_retry_repetition_preserves_policy_identity() -> None:
    first = build_policy_boundary_observation(BASE_RECORD)
    repeated = build_policy_boundary_observation(deepcopy(BASE_RECORD))
    assert repeated.immutable_hash == first.immutable_hash
    assert repeated.provenance == first.provenance


def test_boundary_contains_no_semantic_verdict() -> None:
    observation = build_policy_boundary_observation(BASE_RECORD)
    forbidden = {"SUPPORTED", "REJECTED", "INCONCLUSIVE"}
    assert not forbidden.intersection(observation.__dict__)
    assert not forbidden.intersection(observation.provenance)


def test_core_is_not_part_of_boundary_surface() -> None:
    observation = build_policy_boundary_observation(BASE_RECORD)
    assert "src/jamp" not in observation.__dict__
    assert observation.schema_version == "exp24.policy_boundary_observation.v0"


def test_boundary_requires_no_runtime_or_model_fields() -> None:
    observation = build_policy_boundary_observation(BASE_RECORD)
    assert not hasattr(observation, "model_id")
    assert not hasattr(observation, "model_version")
    assert not hasattr(observation, "runtime")
    assert not hasattr(observation, "provider")
