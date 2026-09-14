"""Minimal run contract v0.1.

A `Run` defines the boundary of a JAMP-like rewrite process.
`run()` only iterates it. All semantics live in the implementation.

Contract notes:

- Query methods (`candidates`, `admissible`, `terminal`) are pure.
  If they raise, `run()` propagates the exception: query failures
  indicate adapter bugs, not runtime conditions.
- Action methods (`strategy`, `apply`) may raise. `run()` catches
  them and returns `StopReason("error", ...)`.
- State is expected to be immutable per step. `apply(state, c)`
  returns a new state; `run()` never mutates what it received.
"""
from __future__ import annotations

from typing import Iterable, NamedTuple, Protocol, TypeVar


S = TypeVar("S")
C = TypeVar("C")


class StopReason(NamedTuple):
    kind: str          # "terminal" | "exhausted" | "budget" | "error"
    detail: str = ""


class RunResult(NamedTuple):
    state: object
    steps: int
    stop_reason: StopReason


class Run(Protocol[S, C]):
    """Structural interface for a runnable JAMP-like process."""

    budget: int

    def initial(self) -> S: ...
    def candidates(self, state: S) -> Iterable[C]: ...
    def admissible(self, state: S, c: C) -> bool: ...
    def apply(self, state: S, c: C) -> S: ...
    def terminal(self, state: S) -> bool: ...
    def strategy(self, state: S, cands: Iterable[C]) -> C: ...


def run(r: Run[S, C]) -> RunResult:
    """Iterate a Run to a stop condition. See module docstring."""
    state = r.initial()
    steps = 0
    while True:
        if r.terminal(state):
            return RunResult(state, steps, StopReason("terminal"))
        if steps >= r.budget:
            return RunResult(state, steps, StopReason("budget"))
        cands = [c for c in r.candidates(state) if r.admissible(state, c)]
        if not cands:
            return RunResult(state, steps, StopReason("exhausted"))
        try:
            chosen = r.strategy(state, cands)
            state = r.apply(state, chosen)
        except Exception as exc:
            return RunResult(state, steps, StopReason("error", repr(exc)))
        steps += 1


__all__ = ["Run", "RunResult", "StopReason", "run"]
