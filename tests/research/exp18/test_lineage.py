"""RED tests for EXP-18 R2.2 multi-hop lineage inspection.

The topology is an explicit research-only adapter over an R1 view.  No
production graph schema is assumed to exist.
"""

from __future__ import annotations

from research.exp18.conflict_node import EpistemicStatus
from research.exp18.dag_query import query_subgraph
from research.exp18.lineage import build_lineage_index, inspect_lineage


def _lineage_view(sample_r0_ledger):
    view = query_subgraph(sample_r0_ledger)
    records = (
        {"node_id": "node_01", "record": view[0], "provenance_raw": "prov-ai-1"},
        {"node_id": "node_02", "record": view[1], "provenance_raw": "prov-ai-2"},
        {"node_id": "node_03", "record": view[2], "provenance_raw": "prov-human"},
    )
    topology_map = {
        "node_01": {"parents": (), "children": ("node_02",)},
        "node_02": {"parents": ("node_01",), "children": ("node_03",)},
        "node_03": {"parents": ("node_02",), "children": ()},
    }
    return records, topology_map


def test_tc_l01_adjacency_index(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    index = build_lineage_index(view, topology_map)

    assert index["node_02"]["parents"] == ("node_01",)
    assert index["node_02"]["children"] == ("node_03",)


def test_tc_l02_direct_relations(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    parents = inspect_lineage(
        view,
        topology_map,
        start_node="node_02",
        direction="parents",
        max_depth=1,
    )
    children = inspect_lineage(
        view,
        topology_map,
        start_node="node_02",
        direction="children",
        max_depth=1,
    )

    assert tuple(item["node_id"] for item in parents) == ("node_01",)
    assert tuple(item["node_id"] for item in children) == ("node_03",)


def test_tc_l03_multi_hop_traversal(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    trace = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=2,
    )

    assert tuple(item["node_id"] for item in trace) == ("node_02", "node_01")


def test_tc_l04_depth_cap(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    trace = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=1,
    )

    assert tuple(item["node_id"] for item in trace) == ("node_02",)


def test_tc_l05_cycle_guard(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)
    topology_map["node_01"] = {"parents": ("node_02",), "children": ("node_02",)}

    trace = inspect_lineage(
        view,
        topology_map,
        start_node="node_01",
        direction="children",
        max_depth=10,
    )

    assert tuple(item["node_id"] for item in trace) == ("node_02", "node_03")


def test_tc_l06_provenance_preservation(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    trace = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=2,
    )

    assert trace[0]["provenance_raw"] == "prov-ai-2"
    assert trace[1]["provenance_raw"] == "prov-ai-1"


def test_tc_l07_conflict_semantics(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)
    context = {"status": EpistemicStatus.INCONCLUSIVE.value, "collision": "CONFLICT"}

    trace = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=2,
        conflict_context=context,
    )

    assert all(item["epistemic_status"] == "INCONCLUSIVE" for item in trace)


def test_tc_l08_anti_scoring(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    trace = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=2,
    )

    forbidden = {"score", "confidence", "rank", "voting_weight"}
    assert all(forbidden.isdisjoint(item) for item in trace)


def test_tc_l09_determinism(sample_r0_ledger):
    view, topology_map = _lineage_view(sample_r0_ledger)

    first = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=2,
    )
    second = inspect_lineage(
        view,
        topology_map,
        start_node="node_03",
        direction="parents",
        max_depth=2,
    )

    assert first == second


def test_tc_l10_scope_isolation():
    from pathlib import Path

    test_path = Path(__file__).resolve()
    assert "tests/research/exp18" in test_path.as_posix()
