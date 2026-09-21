"""RED tests for EXP-18 R2.1 canonical audit export.

These tests intentionally target the not-yet-implemented export layer.
"""

from research.exp18.audit_export import export_audit_manifest, parse_audit_manifest
from research.exp18.dag_query import query_subgraph


def test_tc_e01_byte_determinism(sample_r0_ledger):
    r1_view = query_subgraph(sample_r0_ledger, object_ref="obj_01")
    export_1 = export_audit_manifest(r1_view)
    export_2 = export_audit_manifest(r1_view)
    assert export_1.bytes_payload == export_2.bytes_payload


def test_tc_e02_manifest_stability(sample_r0_ledger):
    r1_view = query_subgraph(sample_r0_ledger, object_ref="obj_01")
    export_1 = export_audit_manifest(r1_view)
    export_2 = export_audit_manifest(r1_view)
    assert export_1.manifest_hash == export_2.manifest_hash


def test_tc_e03_atom_mutation_changes_manifest(sample_r0_ledger):
    view_a = query_subgraph(sample_r0_ledger, object_ref="obj_01")
    view_b = tuple(
        {**item, "value": "mutated"} if index == 0 else item
        for index, item in enumerate(view_a)
    )
    export_a = export_audit_manifest(view_a)
    export_b = export_audit_manifest(view_b)
    assert export_a.manifest_hash != export_b.manifest_hash


def test_tc_e04_source_order_invariance(sample_r0_ledger):
    view = query_subgraph(sample_r0_ledger)
    reversed_view = tuple(reversed(view))
    export_a = export_audit_manifest(view)
    export_b = export_audit_manifest(reversed_view)
    assert export_a.bytes_payload == export_b.bytes_payload
    assert export_a.manifest_hash == export_b.manifest_hash


def test_tc_e05_round_trip_fidelity(sample_r0_ledger):
    r1_view = query_subgraph(sample_r0_ledger, object_ref="obj_01")
    exported = export_audit_manifest(r1_view)
    restored = parse_audit_manifest(exported.bytes_payload)
    assert restored == r1_view


def test_tc_e06_anti_scoring_export(sample_r0_ledger):
    r1_view = query_subgraph(sample_r0_ledger)
    exported = export_audit_manifest(r1_view)
    forbidden = {"score", "confidence", "rank", "voting_weight"}
    assert forbidden.isdisjoint(exported.manifest)
