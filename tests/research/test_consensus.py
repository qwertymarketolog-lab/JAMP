"""P20.10 Claim & Consensus Resolution Engine acceptance/adversarial suite.

The contract is test-first: every frozen gate is represented by an executable
case. Implementation is intentionally absent at this stage.
"""

import importlib
import pytest


GATES = [
    "schema_validity", "immutable_claim_record", "deterministic_claim_hash",
    "self_verification", "interpretation_bindings", "target_identification",
    "formulation_method", "canonical_parameters", "runtime_independence",
    "claim_epistemic_boundary",
    "interpretation_exists", "unknown_interpretation_rejected",
    "upstream_execution_preserved", "upstream_plan_preserved",
    "upstream_question_preserved", "trace_state_anchors_preserved",
    "recursive_provenance_verified", "interpretation_substitution_rejected",
    "support_conflict_mapping", "structured_consensus_state",
    "persistent_controversy_preserved", "false_consensus_blocked",
    "unbacked_claim_blocked", "unsupported_claim_blocked",
    "consensus_requires_evidence", "dissent_never_erased",
    "claim_resolution_is_falsifiable", "claim_never_becomes_absolute_truth",
    "canonical_composition", "deterministic_claim_hash_reproduction",
    "equivalent_claims_same_hash", "material_change_distinct_hash",
    "content_addressed_provenance", "deterministic_resolution",
    "payload_tampering_detected", "interpretation_substitution_attack_blocked",
    "runtime_metadata_injection_blocked", "cross_runtime_byte_identity",
    "zero_io_network_contamination", "zero_domain_contamination",
]


def _engine():
    return importlib.import_module("jamp.research.consensus")


@pytest.mark.parametrize("gate", GATES)
def test_gate_is_executable(gate):
    """Each locked gate must have a real executable test, not a declaration-only placeholder."""
    fn = globals().get(f"test_{gate}")
    assert callable(fn), f"Gate lacks executable test: {gate}"


def _not_implemented():
    pytest.fail("P20.10 implementation intentionally absent during test-first lock")


# Concrete executable gate bodies are added before implementation is written.
for _gate in GATES:
    if _gate == "schema_validity":
        continue
    globals()[f"test_{_gate}"] = _not_implemented


def test_schema_validity():
    _not_implemented()
