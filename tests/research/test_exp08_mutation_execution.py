from __future__ import annotations

from copy import deepcopy

from tests.research.exp08_mutation_execution import collect_raw_observations
from tests.research.exp08_mutation_harness import MUTATION_IDS, baseline_events, mutate


def test_execution_covers_exactly_frozen_mutations() -> None:
    observations = collect_raw_observations()
    assert [item["mutation_id"] for item in observations] == list(MUTATION_IDS)


def test_execution_is_deterministic() -> None:
    assert collect_raw_observations() == collect_raw_observations()


def test_baseline_is_not_modified() -> None:
    baseline = baseline_events()
    baseline_before = deepcopy(baseline)

    for mutation_id in MUTATION_IDS:
        mutated = mutate(baseline, mutation_id)
        assert mutated is not baseline

    assert baseline == baseline_before


def test_each_observation_has_raw_execution_fields() -> None:
    observations = collect_raw_observations()
    required_fields = {
        "mutation_id",
        "input_events",
        "replay_succeeded",
        "exception_type",
        "exception_message",
        "canonical_events",
        "dag_hash",
        "merged_result",
    }

    for observation in observations:
        assert required_fields <= observation.keys()
        assert isinstance(observation["input_events"], list)
        assert observation["input_events"]


def test_failed_replay_is_recorded_not_raised() -> None:
    for observation in collect_raw_observations():
        if not observation["replay_succeeded"]:
            assert observation["exception_type"] is not None
            assert observation["exception_message"] is not None


def test_successful_replay_contains_observable_result() -> None:
    for observation in collect_raw_observations():
        if observation["replay_succeeded"]:
            assert observation["canonical_events"] is not None
            assert observation["dag_hash"] is not None
