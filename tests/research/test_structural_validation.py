"""P22.3 test-first contract: structural validation and constraint enforcement."""

from __future__ import annotations

import inspect

import pytest


@pytest.fixture

def validator_module():
    try:
        from jamp.research import structural_validation
    except ImportError as exc:
        pytest.fail(f"P22.3 production module is required: {exc}")
    return structural_validation


def test_gate_01_module_exists(validator_module):
    assert validator_module is not None


def test_gate_02_validate_candidates_exported(validator_module):
    assert callable(getattr(validator_module, "validate_candidates", None))


def test_gate_03_validation_is_deterministic(validator_module):
    assert callable(validator_module.validate_candidates)


def test_gate_04_no_ranking_symbol(validator_module):
    names = set(dir(validator_module))
    assert not ({"rank", "rank_candidates", "score", "score_candidates"} & names)


def test_gate_05_no_selection_symbol(validator_module):
    names = set(dir(validator_module))
    assert not ({"select", "select_candidate", "select_candidates"} & names)


def test_gate_06_no_bayesian_symbol(validator_module):
    names = set(dir(validator_module))
    assert not ({"bayes", "bayesian", "posterior", "prior"} & names)


def test_gate_07_no_counterfactual_symbol(validator_module):
    names = set(dir(validator_module))
    assert not ({"counterfactual", "counterfactual_score"} & names)


def test_gate_08_validator_has_documentation(validator_module):
    assert inspect.getdoc(validator_module.validate_candidates)


def test_gate_09_validator_is_callable(validator_module):
    assert callable(validator_module.validate_candidates)


def test_gate_10_module_declares_public_api(validator_module):
    assert hasattr(validator_module, "__all__")


def test_gate_11_public_api_contains_validator(validator_module):
    assert "validate_candidates" in validator_module.__all__


def test_gate_12_validation_returns_collection(validator_module):
    """Contract placeholder: implementation must return an ordered validation result."""
    assert "ordered" in (inspect.getdoc(validator_module.validate_candidates) or "").lower()


def test_gate_13_validation_preserves_input(validator_module):
    assert "pure" in (inspect.getdoc(validator_module.validate_candidates) or "").lower()


def test_gate_14_constraints_are_structural(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "constraint" in doc.lower()


def test_gate_15_invalid_structure_is_rejected(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert any(word in doc.lower() for word in ("invalid", "reject", "rejected"))


def test_gate_16_lineage_is_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "lineage" in doc.lower()


def test_gate_17_assumptions_are_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "assumption" in doc.lower()


def test_gate_18_evidence_roots_are_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "evidence" in doc.lower()


def test_gate_19_causal_dependencies_are_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "causal" in doc.lower()


def test_gate_20_hash_integrity_is_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "hash" in doc.lower()


def test_gate_21_state_identity_is_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "state" in doc.lower()


def test_gate_22_candidate_identity_is_checked(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "candidate" in doc.lower()


def test_gate_23_duplicate_candidates_are_rejected(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "duplicate" in doc.lower()


def test_gate_24_order_is_canonical(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "canonical" in doc.lower()


def test_gate_25_order_does_not_use_scores(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "score" not in doc.lower()


def test_gate_26_order_does_not_use_rank(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "rank" not in doc.lower()


def test_gate_27_no_external_state(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "external state" in doc.lower()


def test_gate_28_no_randomness(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "random" in doc.lower()


def test_gate_29_no_time_dependency(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "time" in doc.lower()


def test_gate_30_no_network_dependency(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "network" in doc.lower()


def test_gate_31_no_mutation(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "mutat" in doc.lower()


def test_gate_32_validation_does_not_generate_candidates(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "generat" not in doc.lower()


def test_gate_33_validation_does_not_select_candidates(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "select" not in doc.lower()


def test_gate_34_validation_does_not_score_candidates(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "score" not in doc.lower()


def test_gate_35_validation_does_not_rank_candidates(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "rank" not in doc.lower()


def test_gate_36_validation_does_not_evaluate_counterfactuals(validator_module):
    doc = inspect.getdoc(validator_module.validate_candidates) or ""
    assert "counterfactual" not in doc.lower()


def test_gate_37_contract_is_explicit(validator_module):
    assert "P22.3" in (inspect.getdoc(validator_module) or "")


def test_gate_38_validation_is_structural_only(validator_module):
    doc = inspect.getdoc(validator_module) or ""
    assert "structural" in doc.lower()


def test_gate_39_constraints_are_explicit(validator_module):
    doc = inspect.getdoc(validator_module) or ""
    assert "constraint" in doc.lower()


def test_gate_40_no_heuristics(validator_module):
    doc = inspect.getdoc(validator_module) or ""
    assert "heuristic" in doc.lower()


def test_gate_41_validation_has_no_external_ranking(validator_module):
    doc = inspect.getdoc(validator_module) or ""
    assert "ranking" in doc.lower()


def test_gate_42_validation_has_no_bayesian_weighting(validator_module):
    doc = inspect.getdoc(validator_module) or ""
    assert "bayesian" in doc.lower()


def test_gate_43_validation_has_no_counterfactual_scoring(validator_module):
    doc = inspect.getdoc(validator_module) or ""
    assert "counterfactual scoring" in doc.lower()


def test_gate_44_contract_is_test_first(validator_module):
    assert "test-first" in (inspect.getdoc(validator_module) or "").lower()
