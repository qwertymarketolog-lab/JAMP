"""P22.6 deterministic, immutable state replay primitives.

The replay boundary is intentionally structural: it validates the lineage
commitment, reconstructs the requested ancestor chain in parent-first order,
and returns the content-addressed target identity. It performs no selection,
ranking, scoring, filtering, or environment-dependent work.
"""
from __future__ import annotations

from dataclasses import dataclass

from .lineage_graph import LineageGraph, verify_lineage

__all__ = ("ReplayResult", "replay_state", "verify_replay")


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

    # Verify the cryptographic graph commitment before consulting the target.
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
