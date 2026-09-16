"""Replay Isolation R0 research checks against the existing public replay primitives."""

import random
import time

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.lineage_graph import LineageNode, build_lineage_graph, verify_lineage


def _sample_nodes() -> tuple[LineageNode, ...]:
    root = "a" * 64
    child = "b" * 64
    return (
        LineageNode(root, ()),
        LineageNode(child, (root,)),
    )


def _replay_from_export(exported: dict[str, object]):
    nodes_data = exported["nodes"]
    assert isinstance(nodes_data, list)
    nodes = tuple(
        LineageNode(item["node_hash"], tuple(item["parents"]))
        for item in nodes_data
    )
    graph = build_lineage_graph(nodes)
    assert graph.graph_hash == exported["graph_hash"]
    return graph


def test_ri1_replay_uses_only_exported_artifact() -> None:
    original = build_lineage_graph(_sample_nodes())
    exported = original.export()

    replayed = _replay_from_export(exported)

    assert replayed.export() == exported
    assert verify_lineage(replayed) is True


def test_ri2_replay_is_deterministic() -> None:
    first = build_lineage_graph(_sample_nodes()).export()
    second = build_lineage_graph(tuple(reversed(_sample_nodes()))).export()

    assert first == second
    assert replay_hash(first) == replay_hash(second)


def test_ri3_tampered_artifact_is_rejected() -> None:
    exported = build_lineage_graph(_sample_nodes()).export()
    tampered = dict(exported)
    tampered["graph_hash"] = "f" * 64

    with pytest.raises(ValueError, match="graph hash mismatch"):
        _replay_from_export(tampered)


def test_ri4_replay_is_independent_of_runtime_context(monkeypatch: pytest.MonkeyPatch) -> None:
    exported = build_lineage_graph(_sample_nodes()).export()
    monkeypatch.setenv("JAMP_REPLAY_TEST_CONTEXT", "changed")
    monkeypatch.setattr(time, "time", lambda: 1234567890.0)
    monkeypatch.setattr(random, "random", lambda: 0.999999)

    replayed = _replay_from_export(exported)

    assert replayed.export() == exported


def test_ri5_foreign_artifact_rejection_contract_is_not_defined() -> None:
    """A valid graph has no current namespace/scope marker for 'foreign'."""
    pytest.skip(
        "RI-5 contract gap: lineage_graph has no artifact namespace/scope boundary"
    )
