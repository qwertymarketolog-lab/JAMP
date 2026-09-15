"""Minimal run contract v0.2.

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
- Optional `on_empty` hook is invoked when no candidate is admissible.
  If it returns a new state, the loop continues; if it returns `None`,
  the run stops with `StopReason("exhausted")`. If the hook is absent,
  empty candidate set stops the run with `exhausted` (v0.1 behaviour).
- Two counters are tracked and both exposed in `RunResult`:
    * `steps`       = successful `apply` calls
    * `iterations`  = loop turns that entered the body, including
                      `on_empty` recovery turns. The turn that
                      exits via `terminal()` check is not counted.
  `budget` bounds `iterations`, not `steps`.
- `RunResult.steps` is **not** the same metric as any implementation
  internal history length. Adapters are responsible for their own
  mapping if needed.
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
    iterations: int
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
    iterations = 0
    while True:
        if r.terminal(state):
            return RunResult(state, steps, iterations, StopReason("terminal"))
        if iterations >= r.budget:
            return RunResult(state, steps, iterations, StopReason("budget"))
        iterations += 1
        cands = [c for c in r.candidates(state) if r.admissible(state, c)]
        if not cands:
            on_empty = getattr(r, "on_empty", None)
            if on_empty is None:
                return RunResult(state, steps, iterations, StopReason("exhausted"))
            new_state = on_empty(state)
            if new_state is None:
                return RunResult(state, steps, iterations, StopReason("exhausted"))
            state = new_state
            continue
        try:
            chosen = r.strategy(state, cands)
            state = r.apply(state, chosen)
        except Exception as exc:
            return RunResult(state, steps, iterations, StopReason("error", repr(exc)))
        steps += 1


__all__ = ["Run", "RunResult", "StopReason", "run"]
