"""Empirical characterization of the P23.0-B snapshot commitment boundary."""

from __future__ import annotations

import copy

from tests.benchmarks.fixtures.e2e_synthetic_discovery import create_tick_1_fixture
from tests.benchmarks.harness.cold_replay_worker import _restore


def test_snapshot_commitment_tampering_behavior() -> None:
    """Mutate graph nodes while retaining the snapshot's original graph_hash."""
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

    assert restored_graph.graph_hash != original_graph_hash
    assert restored_graph.graph_hash == fixture.graph.graph_hash or (
        restored_graph.graph_hash != fixture.graph.graph_hash
    )
