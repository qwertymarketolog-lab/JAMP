"""Deterministic causal replay projection for P19.3.

Research-only functionality. The projector reconstructs a verifiable trajectory
from a canonical initial state and a validated P19.2 causal event DAG. It does
not execute arbitrary runtime effects, access jamp.domain, or perform IO.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Sequence

from .canonical import canonical_bytes, replay_hash
from .causal import CausalEvent, topological_order


Transition = Callable[[Any, CausalEvent], Any]


class ReplayError(ValueError):
    """Base error for deterministic replay projection failures."""


class ReplayIntegrityError(ReplayError):
    """Raised when a persisted replay trace does not match its content."""


class ReplayTransitionError(ReplayError):
    """Raised when a transition result does not match its event state anchor."""


class ReplayUnknownEventError(ReplayError):
    """Raised when the transition function cannot interpret an event type."""


@dataclass(frozen=True, slots=True)
class ReplayTrace:
    """Immutable cryptographic identity of one deterministic replay trajectory."""

    initial_state_hash: str
    ordered_event_ids: tuple[str, ...]
    resulting_state_hash: str
    trace_hash: str


def compute_trace_hash(
    initial_state_hash: str,
    ordered_event_ids: Sequence[str],
    resulting_state_hash: str,
) -> str:
    """Return the canonical SHA-256 identity of a complete replay trace."""
    material = {
        "initial_state_hash": initial_state_hash,
        "ordered_event_ids": list(ordered_event_ids),
        "resulting_state_hash": resulting_state_hash,
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _make_trace(
    initial_state_hash: str,
    ordered_event_ids: Sequence[str],
    resulting_state_hash: str,
) -> ReplayTrace:
    event_ids = tuple(ordered_event_ids)
    return ReplayTrace(
        initial_state_hash=initial_state_hash,
        ordered_event_ids=event_ids,
        resulting_state_hash=resulting_state_hash,
        trace_hash=compute_trace_hash(initial_state_hash, event_ids, resulting_state_hash),
    )


def project_replay(
    initial_state: Any,
    events: Sequence[CausalEvent],
    transition: Transition,
) -> ReplayTrace:
    """Project a causal DAG into a deterministic, cryptographically anchored trace.

    ``transition`` must be a deterministic pure function of the supplied state
    and event. Its result is checked against ``event.state_hash`` before it is
    accepted as the next replay state.
    """
    current_state = initial_state
    initial_state_hash = replay_hash(initial_state)
    ordered_events = topological_order(events)

    for event in ordered_events:
        try:
            next_state = transition(current_state, event)
        except ReplayUnknownEventError:
            raise
        except ReplayTransitionError:
            raise
        except Exception as exc:
            raise ReplayTransitionError(
                f"transition failed for event {event.event_id}"
            ) from exc

        try:
            next_state_hash = replay_hash(next_state)
        except Exception as exc:
            raise ReplayTransitionError(
                f"transition produced a non-canonical state for event {event.event_id}"
            ) from exc

        if next_state_hash != event.state_hash:
            raise ReplayTransitionError(
                f"state anchor mismatch for event {event.event_id}: "
                f"expected {event.state_hash}, got {next_state_hash}"
            )
        current_state = next_state

    resulting_state_hash = replay_hash(current_state)
    return _make_trace(
        initial_state_hash,
        (event.event_id for event in ordered_events),
        resulting_state_hash,
    )


def verify_trace(
    trace: ReplayTrace,
    initial_state: Any,
    events: Sequence[CausalEvent],
    transition: Transition,
) -> bool:
    """Recompute a trace from source inputs and reject any integrity mismatch."""
    expected = project_replay(initial_state, events, transition)
    if trace != expected:
        raise ReplayIntegrityError("replay trace integrity failure")
    if trace.trace_hash != compute_trace_hash(
        trace.initial_state_hash,
        trace.ordered_event_ids,
        trace.resulting_state_hash,
    ):
        raise ReplayIntegrityError("replay trace hash integrity failure")
    return True
