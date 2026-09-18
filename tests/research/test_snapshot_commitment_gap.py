"""Normative contract test for the P23.0-B snapshot commitment boundary."""

from __future__ import annotations

import copy

import pytest

from tests.benchmarks.fixtures.e2e_synthetic_discovery import create_tick_1_fixture
from tests.benchmarks.harness.cold_replay_worker import _restore


def test_snapshot_commitment_mismatch_is_rejected() -> None:
    """Require _restore() to reject nodes paired with a stale graph hash."""
    fixture = create_tick_1_fixture()
    payload = {
        "graph": fixture.graph.export(),
        "ledger": fixture.ledger.export(),
        "hypotheses": [fixture.hypothesis_h1.export()],
    }

    restored_graph, _, _ = _restore(payload)
    assert restored_graph.graph_hash == payload["graph"]["graph_hash"]

    tampered_payload = copy.deepcopy(payload)
    tampered_payload["graph"]["nodes"].append(
        {
            "node_hash": "f" * 64,
            "parents": [],
        }
    )
    tampered_payload["graph"]["graph_hash"] = payload["graph"]["graph_hash"]

    with pytest.raises(ValueError):
        _restore(tampered_payload)

