"""P22.6 deterministic, immutable state replay primitives.

The replay boundary is intentionally structural: it validates the lineage
commitment, reconstructs the requested ancestor chain in parent-first order,
and returns the content-addressed target identity.

A narrow P19/P20 compatibility surface is retained for legacy research
artifacts: ``ReplayTrace`` and ``compute_trace_hash`` are structural helpers
used by the immutable artifact registry. They do not alter the P22.6 replay
state API or perform selection, ranking, scoring, filtering, or I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Sequence

from .canonical import canonical_bytes
from .lineage_graph import LineageGraph, verify_lineage

__all__ = (
    "ReplayTrace",
    "compute_trace_hash",
    "ReplayResult",
    "replay_state",
    "verify_replay",
)


@dataclass(frozen=True, slots=True)
class ReplayTrace:
    """Legacy immutable identity of one deterministic replay trajectory."""

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


@dataclass(frozen=True)
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
