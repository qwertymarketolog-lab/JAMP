"""Deterministic Phase A state machine.

The runner owns state transitions; an LLM, when later connected, may only
propose an action and cannot mutate state directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class State(StrEnum):
    BOOTSTRAP = "BOOTSTRAP"
    LOAD_TASK = "LOAD_TASK"
    HYPOTHESIS = "HYPOTHESIS"
    PLAN = "PLAN"
    DISPATCH = "DISPATCH"
    AWAIT_CI = "AWAIT_CI"
    RECONCILE = "RECONCILE"
    TERMINAL = "TERMINAL"


class TransitionError(ValueError):
    """Raised when a requested transition is not in the deterministic graph."""


_TRANSITIONS = {
    State.BOOTSTRAP: {State.LOAD_TASK},
    State.LOAD_TASK: {State.HYPOTHESIS},
    State.HYPOTHESIS: {State.PLAN},
    State.PLAN: {State.DISPATCH},
    State.DISPATCH: {State.AWAIT_CI},
    State.AWAIT_CI: {State.RECONCILE},
    State.RECONCILE: {State.TERMINAL},
    State.TERMINAL: set(),
}


@dataclass(frozen=True)
class RunnerState:
    state: State


def transition(current: RunnerState, target: State) -> RunnerState:
    if target not in _TRANSITIONS[current.state]:
        raise TransitionError(f"invalid transition: {current.state} -> {target}")
    return RunnerState(target)
