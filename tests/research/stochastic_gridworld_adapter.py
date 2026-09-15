from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
    actual_outcome: str
    is_deviated: bool
    state_after: StateSnapshot
    blocked: bool


@dataclass(frozen=True)
class StochasticGridworldState:
    agent_pos: tuple[int, int] = (0, 0)
    rng_state: int = 1
    step_count: int = 0
    events: tuple[Event, ...] = ()
    intended_sequence: tuple[str, ...] = (
        "MOVE_EAST",
        "MOVE_EAST",
        "MOVE_EAST",
        "MOVE_EAST",
        "MOVE_EAST",
        "MOVE_EAST",
    )


class StochasticGridworldAdapter:
    budget = 6

    OFFSETS = {
        "MOVE_NORTH": (0, 1),
        "MOVE_SOUTH": (0, -1),
        "MOVE_EAST": (1, 0),
        "MOVE_WEST": (-1, 0),
    }

    LEFT_DEVIATION = {
        "MOVE_NORTH": "MOVE_WEST",
        "MOVE_EAST": "MOVE_NORTH",
        "MOVE_SOUTH": "MOVE_EAST",
        "MOVE_WEST": "MOVE_SOUTH",
    }

    RIGHT_DEVIATION = {
        "MOVE_NORTH": "MOVE_EAST",
        "MOVE_EAST": "MOVE_SOUTH",
        "MOVE_SOUTH": "MOVE_WEST",
        "MOVE_WEST": "MOVE_NORTH",
    }

    @staticmethod
    def _next_rng(state: int) -> tuple[int, float]:
        """Frozen EXP-05 scenario PRNG: modulus 2^31, denominator 2^31."""
        next_state = (1103515245 * state + 12345) % (2**31)
        value = next_state / (2**31)
        return next_state, value

    @staticmethod
    def _snapshot(state: StochasticGridworldState) -> StateSnapshot:
        return StateSnapshot(state.agent_pos, state.rng_state, state.step_count)

    def initial(self) -> StochasticGridworldState:
        return StochasticGridworldState()

    def candidates(self, state: StochasticGridworldState) -> Iterable[str]:
        if state.step_count >= len(state.intended_sequence):
            return ()
        return (state.intended_sequence[state.step_count],)

    def admissible(self, state: StochasticGridworldState, action: str) -> bool:
        return action in self.OFFSETS

    def strategy(self, state: StochasticGridworldState, candidates: Iterable[str]) -> str:
        return next(iter(candidates))

    def apply(
        self, state: StochasticGridworldState, action: str
    ) -> StochasticGridworldState:
        state_before = self._snapshot(state)
        next_rng, roll = self._next_rng(state.rng_state)

        if roll < 0.8:
            actual = action
        elif roll < 0.9:
            actual = self.LEFT_DEVIATION[action]
        else:
            actual = self.RIGHT_DEVIATION[action]

        dx, dy = self.OFFSETS[actual]
        candidate_pos = (
            state.agent_pos[0] + dx,
            state.agent_pos[1] + dy,
        )
        new_pos = (
            max(0, min(2, candidate_pos[0])),
            max(0, min(2, candidate_pos[1])),
        )
        blocked = new_pos != candidate_pos

        state_after = StateSnapshot(new_pos, next_rng, state.step_count + 1)
        event = Event(
            step=state.step_count + 1,
            state_before=state_before,
            intended_action=action,
            actual_outcome=actual,
            is_deviated=(actual != action),
            state_after=state_after,
            blocked=blocked,
        )

        return StochasticGridworldState(
            agent_pos=new_pos,
            rng_state=next_rng,
            step_count=state.step_count + 1,
            events=state.events + (event,),
            intended_sequence=state.intended_sequence,
        )

    def terminal(self, state: StochasticGridworldState) -> bool:
        return state.step_count >= len(state.intended_sequence)
