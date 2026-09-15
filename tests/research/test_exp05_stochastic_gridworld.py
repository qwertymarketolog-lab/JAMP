from __future__ import annotations

import hashlib
from pathlib import Path

from jamp.run import run

from tests.research.stochastic_gridworld_adapter import (
    StateSnapshot,
    StochasticGridworldAdapter,
    StochasticGridworldState,
)


EXPECTED_CORE_BLOB_SHA = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"


def compute_git_blob_sha1(filepath: Path) -> str:
    content = filepath.read_bytes()
    header = f"blob {len(content)}\x00".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


class SeededStochasticGridworldAdapter(StochasticGridworldAdapter):
    def __init__(self, seed: int):
        self.seed = seed

    def initial(self) -> StochasticGridworldState:
        return StochasticGridworldState(rng_state=self.seed)


def execute(seed: int):
    return run(SeededStochasticGridworldAdapter(seed))


def test_core_immutability_git_blob_sha1():
    core_path = Path("src/jamp/run.py")
    assert core_path.exists(), "src/jamp/run.py file must exist"
    assert compute_git_blob_sha1(core_path) == EXPECTED_CORE_BLOB_SHA


def test_exp05a_seed1_atomic_stochastic_interaction():
    result = execute(1)
    state = result.state

    assert result.stop_reason.kind == "terminal"
    assert result.steps == 6
    assert len(state.events) == 6

    assert all(event.intended_action == "MOVE_EAST" for event in state.events)
    assert state.events[4].actual_outcome == "MOVE_SOUTH"
    assert state.events[4].is_deviated is True
    assert any(event.is_deviated for event in state.events)

    previous_after = None
    for event in state.events:
        if previous_after is None:
            assert event.state_before == StateSnapshot((0, 0), 1, 0)
        else:
            assert event.state_before == previous_after
        assert event.intended_by == "agent"
        assert event.outcome_from == "environment"
        assert event.is_deviated == (event.actual_outcome != event.intended_action)
        assert event.state_after.step_count == event.state_before.step_count + 1
        previous_after = event.state_after

    assert state.events[-1].state_after == StateSnapshot(
        state.agent_pos, state.rng_state, state.step_count
    )


def test_exp05b_replay_determinism_for_each_seed():
    seed1_run1 = execute(1)
    seed1_run2 = execute(1)
    seed2_run1 = execute(2)
    seed2_run2 = execute(2)

    assert seed1_run1.steps == seed1_run2.steps == 6
    assert seed2_run1.steps == seed2_run2.steps == 6
    assert seed1_run1.state == seed1_run2.state
    assert seed2_run1.state == seed2_run2.state

    # Frozen vector observation: seed 2 has no deviation in its first five
    # interactions. The sixth outcome is observed, not prescribed here.
    assert all(not event.is_deviated for event in seed2_run1.state.events[:5])
    assert seed2_run1.state.events[5].actual_outcome in {
        "MOVE_EAST",
        "MOVE_NORTH",
        "MOVE_SOUTH",
        "MOVE_WEST",
    }


def test_exp05_provenance_contains_complete_atomic_interactions():
    result = execute(1)
    state = result.state

    assert state.events[0].state_before.agent_pos == (0, 0)
    for event in state.events:
        assert event.intended_by == "agent"
        assert event.outcome_from == "environment"
        assert event.intended_action == "MOVE_EAST"
        assert event.actual_outcome in {
            "MOVE_EAST",
            "MOVE_NORTH",
            "MOVE_SOUTH",
            "MOVE_WEST",
        }
        assert event.is_deviated == (event.actual_outcome != event.intended_action)
        assert event.state_after.agent_pos[0] in range(3)
        assert event.state_after.agent_pos[1] in range(3)
