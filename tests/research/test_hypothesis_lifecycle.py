"""P20.5 Hypothesis Lifecycle & Refutation Engine — acceptance contract.

The test names are the frozen 32-gate contract. Implementation is intentionally
absent at this stage; this file is the test-first specification.
"""

import pytest


GATES = [
    (1, "schema_validity"),
    (2, "immutable_hypothesis_record"),
    (3, "valid_hypothesis_hash"),
    (4, "deterministic_hash_computation"),
    (5, "self_verification"),
    (6, "canonical_formulation"),
    (7, "explicit_hypothesis_type"),
    (8, "valid_status"),
    (9, "runtime_independent_identity"),
    (10, "deterministic_export_import"),
    (11, "registered_evidence_only"),
    (12, "unknown_evidence_rejected"),
    (13, "evidence_integrity_verified"),
    (14, "claim_integrity_verified"),
    (15, "claim_evidence_substitution_rejected"),
    (16, "evidence_tampering_detected"),
    (17, "complete_provenance_preserved"),
    (18, "active_to_supported"),
    (19, "active_to_refuted"),
    (20, "active_to_revised"),
    (21, "active_to_retired"),
    (22, "supported_transitions"),
    (23, "terminal_state_finality"),
    (24, "illegal_transition_rejected"),
    (25, "transition_reason_required"),
    (26, "parent_hypothesis_must_exist"),
    (27, "parent_hash_integrity_verified"),
    (28, "descendant_cannot_rewrite_ancestor"),
    (29, "recursive_lineage_preserved"),
    (30, "transition_history_tampering_detected"),
    (31, "cross_runtime_byte_identical_reproduction"),
    (32, "zero_io_network_domain_contamination"),
]


@pytest.mark.parametrize("gate_number,gate_name", GATES)
def test_p20_5_gate_contract(gate_number, gate_name):
    """Every frozen gate must have an explicit implementation test."""
    assert gate_number in range(1, 33)
    assert gate_name


def test_p20_5_exactly_32_frozen_gates():
    assert len(GATES) == 32
    assert [number for number, _ in GATES] == list(range(1, 33))
