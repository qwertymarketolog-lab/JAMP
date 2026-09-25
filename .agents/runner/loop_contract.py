"""Fail-closed state machine for Autonomous Research Loop v0."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LoopState(StrEnum):
    OPEN = "OPEN"
    RUNNING = "RUNNING"
    AWAIT_CI = "AWAIT_CI"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    HOLD = "HOLD"
    CLOSED = "CLOSED"


_ALLOWED = {
    LoopState.OPEN: frozenset({LoopState.RUNNING, LoopState.HOLD}),
    LoopState.RUNNING: frozenset(
        {LoopState.AWAIT_CI, LoopState.FAILED, LoopState.HOLD}
    ),
    LoopState.AWAIT_CI: frozenset(
        {
            LoopState.VERIFIED,
            LoopState.FAILED,
            LoopState.INCONCLUSIVE,
            LoopState.HOLD,
        }
    ),
    LoopState.VERIFIED: frozenset({LoopState.CLOSED, LoopState.HOLD}),
    LoopState.FAILED: frozenset(
        {LoopState.RUNNING, LoopState.HOLD, LoopState.CLOSED}
    ),
    LoopState.INCONCLUSIVE: frozenset(
        {LoopState.RUNNING, LoopState.HOLD, LoopState.CLOSED}
    ),
    LoopState.HOLD: frozenset({LoopState.RUNNING, LoopState.CLOSED}),
    LoopState.CLOSED: frozenset(),
}


@dataclass(frozen=True)
class LoopTransition:
    previous: LoopState
    current: LoopState
    evidence: tuple[str, ...]


def transition(
    previous: LoopState,
    current: LoopState,
    *,
    evidence: tuple[str, ...],
) -> LoopTransition:
    """Permit only declared transitions with non-empty evidence."""
    if current not in _ALLOWED[previous]:
        raise ValueError(f"invalid transition: {previous} -> {current}")
    if not evidence or any(not item.strip() for item in evidence):
        raise ValueError("state transition requires evidence")
    return LoopTransition(previous, current, evidence)
