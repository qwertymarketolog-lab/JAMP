"""EXP-Bridge R0: execution-artifact projection and ledger binding tests.

The local adapter fixture is copied from the frozen historical EXP-05 adapter
blob 907ecd9f257b338bf0dd1413edafefc3129ec960. It stays inside this research
test so the bridge does not resurrect production/domain code or modify Run
Core.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jamp.research.canonical import canonical_bytes, replay_hash
from jamp.research.causal_ledger import CausalLedger
from jamp.run import run


@dataclass(frozen=True)
class StateSnapshot:
    agent_pos: tuple[int, int]
    rng_state: int
    step_count: int


@dataclass(frozen=True)
class Event:
    step: int
    state_before: StateSnapshot
    intended_action: str
    intended_by: str
    actual_outcome: str
    outcome_from: str
    is_deviated: bool
    state_after: StateSnapshot
    blocked: bool


@dataclass(frozen=True)
class StochasticGridworldState:
    agent_pos: tuple[int, int]
    rng_state: int
    step_count: int
    events: tuple[Event, ...]
    intended_sequence: tuple[str, ...]


class StochasticGridworldAdapter:
    budget = 6

    OFFSETS = {
        "MOVE_NORTH": (-1, 0),
        "MOVE_SOUTH": (1, 0),
        "MOVE_EAST": (0, 1),
        "MOVE_WEST": (0, -1),
    }
    LEFT_DEVIATION = {
        "MOVE_NORTH": "MOVE_WEST",
        "MOVE_SOUTH": "MOVE_EAST",
        "MOVE_EAST": "MOVE_NORTH",
        "MOVE_WEST": "MOVE_SOUTH",
    }
    RIGHT_DEVIATION = {
        "MOVE_NORTH": "MOVE_EAST",
        "MOVE_SOUTH": "MOVE_WEST",
        "MOVE_EAST": "MOVE_SOUTH",
        "MOVE_WEST": "MOVE_NORTH",
    }

    @staticmethod
    def _next_rng(state: int) -> int:
        return (1103515245 * state + 12345) % (2**31)

    def initial(self) -> StochasticGridworldState:
        return StochasticGridworldState(
            agent_pos=(0, 0),
            rng_state=1,
            step_count=0,
            events=(),
            intended_sequence=("MOVE_EAST",) * self.budget,
        )

    def candidates(self, state: StochasticGridworldState) -> tuple[str, ...]:
        return (state.intended_sequence[state.step_count],)

    def admissible(
        self, state: StochasticGridworldState, action: str
    ) -> bool:
        return action in self.OFFSETS

    def strategy(
        self, state: StochasticGridworldState, candidates: tuple[str, ...]
    ) -> str:
        return candidates[0]

    def apply(
        self, state: StochasticGridworldState, action: str
    ) -> StochasticGridworldState:
        state_before = StateSnapshot(
            agent_pos=state.agent_pos,
            rng_state=state.rng_state,
            step_count=state.step_count,
        )
        rng_state = self._next_rng(state.rng_state)
        sample = rng_state / (2**31)
        if sample < 0.8:
            actual_outcome = action
        elif sample < 0.9:
            actual_outcome = self.LEFT_DEVIATION[action]
        else:
            actual_outcome = self.RIGHT_DEVIATION[action]

        row, col = state.agent_pos
        delta_row, delta_col = self.OFFSETS[actual_outcome]
        next_row = min(2, max(0, row + delta_row))
        next_col = min(2, max(0, col + delta_col))
        next_pos = (next_row, next_col)
        blocked = next_pos == state.agent_pos
        state_after = StateSnapshot(
            agent_pos=next_pos,
            rng_state=rng_state,
            step_count=state.step_count + 1,
        )
        event = Event(
            step=state.step_count + 1,
            state_before=state_before,
            intended_action=action,
            intended_by="agent",
            actual_outcome=actual_outcome,
            outcome_from="environment",
            is_deviated=actual_outcome != action,
            state_after=state_after,
            blocked=blocked,
        )
        return StochasticGridworldState(
            agent_pos=next_pos,
            rng_state=rng_state,
            step_count=state.step_count + 1,
            events=state.events + (event,),
            intended_sequence=state.intended_sequence,
        )

    def terminal(self, state: StochasticGridworldState) -> bool:
        return state.step_count >= len(state.intended_sequence)


class SeededStochasticGridworldAdapter(StochasticGridworldAdapter):
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def initial(self) -> StochasticGridworldState:
        state = super().initial()
        return StochasticGridworldState(
            agent_pos=state.agent_pos,
            rng_state=self.seed,
            step_count=state.step_count,
            events=state.events,
            intended_sequence=state.intended_sequence,
        )


def _state_snapshot(state: StateSnapshot) -> dict[str, object]:
    return {
        "agent_pos": list(state.agent_pos),
        "rng_state": state.rng_state,
        "step_count": state.step_count,
    }


def _event(event: Event) -> dict[str, object]:
    return {
        "step": event.step,
        "state_before": _state_snapshot(event.state_before),
        "intended_action": event.intended_action,
        "intended_by": event.intended_by,
        "actual_outcome": event.actual_outcome,
        "outcome_from": event.outcome_from,
        "is_deviated": event.is_deviated,
        "state_after": _state_snapshot(event.state_after),
        "blocked": event.blocked,
    }


def _artifact(result: object, seed: int) -> dict[str, object]:
    state = result.state  # type: ignore[attr-defined]
    return {
        "artifact_version": "0",
        "experiment_ref": "EXP-05",
        "seed": seed,
        "steps": result.steps,  # type: ignore[attr-defined]
        "final_state": _state_snapshot(state),
        "events": [_event(event) for event in state.events],
    }


def _execute(seed: int) -> object:
    return run(SeededStochasticGridworldAdapter(seed))


def test_bridge_r0_t1_determinism() -> None:
    result1 = _execute(1)
    result2 = _execute(1)
    artifact1 = _artifact(result1, 1)
    artifact2 = _artifact(result2, 1)

    assert canonical_bytes(artifact1) == canonical_bytes(artifact2)
    assert replay_hash(artifact1) == replay_hash(artifact2)


def test_bridge_r0_t2_semantic_sensitivity() -> None:
    artifact = _artifact(_execute(1), 1)
    mutated = {
        **artifact,
        "events": [
            {**artifact["events"][0], "actual_outcome": "MOVE_NORTH"},
            *artifact["events"][1:],
        ],
    }

    assert replay_hash(mutated) != replay_hash(artifact)


def test_bridge_r0_t3_ledger_binding() -> None:
    artifact = _artifact(_execute(1), 1)
    result_ref = replay_hash(artifact)

    ledger = CausalLedger()
    ledger.append_genesis()
    prediction = ledger.append_prediction_commit("1" * 64)
    execution_start = ledger.append_execution_start(
        prediction.event_hash, "bridge-r0-seed-1"
    )
    execution_result = ledger.append_execution_result(
        execution_start.event_hash, result_ref
    )

    assert ledger.get(execution_result.event_hash) == execution_result
    assert execution_result.payload_hash == replay_hash(
        {
            "execution_start_hash": execution_start.event_hash,
            "result_ref": result_ref,
        }
    )
    assert ledger.head == execution_result.event_hash


def test_bridge_r0_t4_ledger_blindness() -> None:
    ledger_source = Path(
        "src/jamp/research/causal_ledger.py"
    ).read_text(encoding="utf-8")

    assert "StochasticGridworld" not in ledger_source
    assert "intended_action" not in ledger_source
    assert "actual_outcome" not in ledger_source
    assert "is_deviated" not in ledger_source
