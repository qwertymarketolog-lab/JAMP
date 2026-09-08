from dataclasses import dataclass
import hashlib

import pytest

from jamp.research.canonical import canonical_bytes, canonical_json, replay_hash


@dataclass(frozen=True)
class FrozenState:
    baseline_commit: str
    random_seed: int
    input_vector: tuple[int, ...]


def test_dict_insertion_order_does_not_change_hash() -> None:
    first = {"a": 1, "b": 2, "nested": {"x": True, "y": None}}
    second = {"nested": {"y": None, "x": True}, "b": 2, "a": 1}
    assert replay_hash(first) == replay_hash(second)
    assert canonical_json(first) == canonical_json(second)


def test_frozen_dataclass_is_canonicalized() -> None:
    state = FrozenState("c24a073495aed11104112d14863d060a3aa7528e", 42, (1, 2, 3))
    assert replay_hash(state) == replay_hash(
        {
            "baseline_commit": "c24a073495aed11104112d14863d060a3aa7528e",
            "random_seed": 42,
            "input_vector": [1, 2, 3],
        }
    )


def test_numeric_normalization_is_stable() -> None:
    assert replay_hash({"value": 1}) == replay_hash({"value": 1.0})
    assert replay_hash({"value": -0.0}) == replay_hash({"value": 0})


def test_mutating_experiment_state_changes_hash() -> None:
    state = {
        "baseline_commit": "c24a073495aed11104112d14863d060a3aa7528e",
        "random_seed": 42,
        "input_vector": [1, 2, 3],
    }
    baseline = replay_hash(state)
    assert replay_hash({**state, "random_seed": 43}) != baseline
    assert replay_hash({**state, "baseline_commit": "other"}) != baseline
    assert replay_hash({**state, "input_vector": [1, 2, 4]}) != baseline


def test_runtime_metadata_does_not_change_hash() -> None:
    state = {
        "baseline_commit": "c24a073495aed11104112d14863d060a3aa7528e",
        "random_seed": 42,
        "input_vector": [1, 2, 3],
    }
    with_runtime = {
        **state,
        "execution_timestamp": "2026-09-08T16:00:00Z",
        "runner_id": "runner-123",
        "telemetry": {"duration_ms": 17},
    }
    assert replay_hash(state) == replay_hash(with_runtime)


def test_path_metadata_does_not_bind_hash_to_host() -> None:
    left = {"input": {"path": "/home/alice/work/input.json"}}
    right = {"input": {"path": "C:\\Users\\bob\\work\\input.json"}}
    assert replay_hash(left) == replay_hash(right)


def test_non_string_dictionary_keys_are_rejected() -> None:
    with pytest.raises(TypeError, match="dictionary keys must be strings"):
        canonical_bytes({1: "invalid"})


def test_non_finite_numbers_are_rejected() -> None:
    with pytest.raises(ValueError, match="NaN or infinity"):
        replay_hash({"value": float("nan")})
    with pytest.raises(ValueError, match="NaN or infinity"):
        replay_hash({"value": float("inf")})


def test_hash_is_sha256_of_canonical_utf8_bytes() -> None:
    state = {"message": "JAMP — replay"}
    expected = hashlib.sha256(canonical_bytes(state)).hexdigest()
    assert replay_hash(state) == expected
