"""Deterministic replay primitives with backward-compatible research contracts.

The P22.6 state-replay API remains the active lineage-based boundary. The
P19/P20 replay projection surface is retained as a compatibility layer for
historical research artifacts and diagnostics. Both surfaces are immutable,
deterministic, content-addressed, and free of I/O and environment-dependent
selection logic.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Sequence

from .canonical import canonical_bytes, replay_hash
from .causal import CausalEvent, topological_order
from .lineage_graph import LineageGraph, verify_lineage


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
    """Project a causal DAG into a deterministic, cryptographically anchored trace."""
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


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Immutable result of deterministic replay for one lineage target."""

    state_hash: str
    lineage: tuple[str, ...]

    def export(self) -> dict[str, object]:
        """Return a detached structural representation."""
        return {
            "state_hash": self.state_hash,
            "lineage": list(self.lineage),
        }


def replay_state(graph: LineageGraph, target_hash: str) -> ReplayResult:
    """Reconstruct a target state from its validated parent-first lineage."""
    if not isinstance(graph, LineageGraph):
        raise TypeError("graph must be a LineageGraph")

    verify_lineage(graph)
    try:
        lineage = graph.traverse(target_hash)
    except KeyError as exc:
        raise ValueError("replay target is not present in the lineage graph") from exc
    if not lineage or lineage[-1] != target_hash:
        raise ValueError("replay target is not the terminal lineage state")

    return ReplayResult(state_hash=target_hash, lineage=lineage)


def verify_replay(graph: LineageGraph, result: ReplayResult) -> bool:
    """Verify a replay result against the immutable lineage commitment."""
    if not isinstance(graph, LineageGraph):
        raise TypeError("graph must be a LineageGraph")
    if not isinstance(result, ReplayResult):
        raise TypeError("result must be a ReplayResult")

    verify_lineage(graph)
    try:
        expected = graph.traverse(result.state_hash)
    except KeyError as exc:
        raise ValueError("replay state hash is not present in the lineage graph") from exc
    if result.lineage != expected:
        raise ValueError("replay lineage mismatch")
    if not result.lineage or result.state_hash != result.lineage[-1]:
        raise ValueError("replay state hash mismatch")
    return True


# Keep the P22.6 public export contract exact; compatibility symbols remain
# importable for historical P19/P20 research modules without being advertised
# as part of the current state-replay API.
__all__ = ("ReplayResult", "replay_state", "verify_replay")
