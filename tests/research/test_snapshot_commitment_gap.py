"""Empirical characterization of the P23.0-B snapshot commitment boundary."""

from __future__ import annotations

import copy

from tests.benchmarks.fixtures.e2e_synthetic_discovery import create_tick_1_fixture
from tests.benchmarks.harness.cold_replay_worker import _restore


def test_snapshot_commitment_tampering_behavior() -> None:
    """Record whether _restore() rejects or accepts a stale graph commitment."""
    fixture = create_tick_1_fixture()
    payload = {
        "graph": fixture.graph.export(),
        "ledger": fixture.ledger.export(),
        "hypotheses": [fixture.hypothesis_h1.export()],
    }

    original_graph_hash = payload["graph"]["graph_hash"]
    tampered_payload = copy.deepcopy(payload)
    tampered_payload["graph"]["nodes"].append(
        {
            "node_hash": "f" * 64,
            "parents": [],
        }
    )
    tampered_payload["graph"]["graph_hash"] = original_graph_hash

    restored_graph, _, _ = _restore(tampered_payload)

    # Empirical outcome: _restore() accepts the tampered nodes and reconstructs
    # a different commitment without comparing it with the stale snapshot hash.
    assert len(restored_graph.nodes) == len(fixture.graph.nodes) + 1
    assert restored_graph.graph_hash != original_graph_hash
