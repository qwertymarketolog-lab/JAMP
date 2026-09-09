"""P22.3 executable contract: structural validation and constraint enforcement."""

from __future__ import annotations

import inspect
from dataclasses import replace

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.search_space import Hypothesis, SearchSpaceError, SearchState

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def make_state(*, claims=("x=1",), depth=0, constraints=(), assumptions=("A",),
               evidence_root=SHA_A, causal_root=SHA_B, support=(SHA_C,),
               contradicting=(), causal=(SHA_B,)):
    h = Hypothesis(tuple(claims), tuple(support), tuple(contradicting), tuple(assumptions), tuple(causal), ("do(x)",))
    return SearchState(evidence_root, causal_root, (h,), tuple(constraints), tuple(assumptions), depth)


@pytest.fixture
def validator_module():
    try:
        from jamp.research import structural_validation
    except ImportError as exc:
        pytest.fail(f"P22.3 production module is required: {exc}")
    return structural_validation


def valid_pair():
    parent = make_state()
    child = make_state(depth=1)
    return parent, child


def test_gate_01_module_exists(validator_module): assert validator_module

def test_gate_02_public_validator_exists(validator_module): assert callable(validator_module.validate_candidates)

def test_gate_03_public_single_validator_exists(validator_module): assert callable(validator_module.validate_candidate)

def test_gate_04_signature_is_parent_candidates(validator_module):
    assert list(inspect.signature(validator_module.validate_candidates).parameters) == ["parent", "candidates"]

def test_gate_05_valid_candidate_passes(validator_module):
    p, c = valid_pair(); assert validator_module.validate_candidates(p, (c,)) == (c,)

def test_gate_06_empty_candidates_pass(validator_module):
    p, _ = valid_pair(); assert validator_module.validate_candidates(p, ()) == ()

def test_gate_07_single_validator_passes(validator_module):
    p, c = valid_pair(); assert validator_module.validate_candidate(p, c) is c

def test_gate_08_parent_hash_integrity_checked(validator_module):
    p, _ = valid_pair(); object.__setattr__(p, "state_hash", "0" * 64)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, ())

def test_gate_09_candidate_hash_integrity_checked(validator_module):
    p, c = valid_pair(); object.__setattr__(c, "state_hash", "0" * 64)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_10_parent_type_checked(validator_module):
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(object(), ())

def test_gate_11_candidate_type_checked(validator_module):
    p, _ = valid_pair()
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (object(),))

def test_gate_12_evidence_root_must_match(validator_module):
    p, _ = valid_pair(); c = make_state(depth=1, evidence_root=SHA_B)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_13_causal_root_must_match(validator_module):
    p, _ = valid_pair(); c = make_state(depth=1, causal_root=SHA_C, causal=(SHA_C,))
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_14_state_assumptions_must_be_preserved(validator_module):
    p = make_state(assumptions=("A", "B")); c = make_state(depth=1, assumptions=("A",))
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_15_hypothesis_assumptions_must_be_preserved(validator_module):
    p = make_state(assumptions=("A", "B"))
    h = Hypothesis(("x=1",), (SHA_C,), (), ("A",), (SHA_B,), ("do(x)",))
    c = SearchState(SHA_A, SHA_B, (h,), ("A", "B"), ("A", "B"), 1)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_16_causal_dependencies_must_be_preserved(validator_module):
    p, _ = valid_pair(); c = make_state(depth=1, causal=())
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_17_supporting_evidence_must_not_be_lost(validator_module):
    p, _ = valid_pair(); c = make_state(depth=1, support=())
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_18_contradicting_evidence_is_rejected(validator_module):
    p, _ = valid_pair(); c = make_state(depth=1, contradicting=(SHA_A,))
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_19_depth_advances_exactly_one(validator_module):
    p, _ = valid_pair(); c = make_state(depth=2)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_20_depth_cannot_decrease(validator_module):
    p = make_state(depth=1); c = make_state(depth=0)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_21_depth_bound_is_enforced(validator_module):
    p = make_state(depth=0, constraints=("depth<=0",)); c = make_state(depth=1, constraints=("depth<=0",))
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_22_constraints_must_be_preserved(validator_module):
    p = make_state(constraints=("depth<=2",)); c = make_state(depth=1)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_23_parentage_is_structural(validator_module):
    p, _ = valid_pair(); c = make_state(depth=1, evidence_root=SHA_C, causal_root=SHA_C, causal=(SHA_C,))
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_24_parent_is_not_a_candidate(validator_module):
    p, _ = valid_pair()
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (p,))

def test_gate_25_duplicate_candidates_rejected(validator_module):
    p, c = valid_pair()
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c, c))

def test_gate_26_result_is_tuple(validator_module):
    p, c = valid_pair(); assert isinstance(validator_module.validate_candidates(p, (c,)), tuple)

def test_gate_27_result_is_canonically_ordered(validator_module):
    p = make_state(); a = make_state(claims=("a",), depth=1); b = make_state(claims=("b",), depth=1)
    result = validator_module.validate_candidates(p, (b, a))
    assert tuple(x.state_hash for x in result) == tuple(sorted((a.state_hash, b.state_hash)))

def test_gate_28_input_order_does_not_change_result(validator_module):
    p = make_state(); a = make_state(claims=("a",), depth=1); b = make_state(claims=("b",), depth=1)
    assert validator_module.validate_candidates(p, (a, b)) == validator_module.validate_candidates(p, (b, a))

def test_gate_29_candidate_identity_is_preserved(validator_module):
    p, c = valid_pair(); assert validator_module.validate_candidates(p, (c,))[0] is c

def test_gate_30_parent_is_not_mutated(validator_module):
    p, _ = valid_pair(); snapshot = p.export(); validator_module.validate_candidates(p, ()); assert p.export() == snapshot

def test_gate_31_candidate_is_not_mutated(validator_module):
    p, c = valid_pair(); snapshot = c.export(); validator_module.validate_candidates(p, (c,)); assert c.export() == snapshot

def test_gate_32_hash_identity_matches_canonical_export(validator_module):
    p, c = valid_pair(); assert c.state_hash == replay_hash(c.export()); assert validator_module.validate_candidates(p, (c,))[0].state_hash == c.state_hash

def test_gate_33_invalid_candidate_hash_is_rejected(validator_module):
    p, c = valid_pair(); object.__setattr__(c, "state_hash", "f" * 64)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, (c,))

def test_gate_34_invalid_parent_hash_is_rejected(validator_module):
    p, _ = valid_pair(); object.__setattr__(p, "state_hash", "f" * 64)
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, ())

def test_gate_35_candidates_must_be_iterable(validator_module):
    p, _ = valid_pair()
    with pytest.raises(SearchSpaceError): validator_module.validate_candidates(p, None)

def test_gate_36_no_score_api(validator_module):
    assert not hasattr(validator_module, "score_candidates") and not hasattr(validator_module, "score")

def test_gate_37_no_rank_api(validator_module):
    assert not hasattr(validator_module, "rank_candidates") and not hasattr(validator_module, "rank")

def test_gate_38_no_selection_api(validator_module):
    assert not hasattr(validator_module, "select_candidates") and not hasattr(validator_module, "select")

def test_gate_39_no_counterfactual_api(validator_module):
    assert not hasattr(validator_module, "counterfactual")

def test_gate_40_no_bayesian_api(validator_module):
    names = set(dir(validator_module)); assert not {"bayesian", "posterior", "prior"} & names

def test_gate_41_no_random_module_import(validator_module):
    assert "random" not in inspect.getsource(validator_module).lower()

def test_gate_42_no_external_ranking_dependency(validator_module):
    source = inspect.getsource(validator_module).lower(); assert not any(x in source for x in ("sklearn", "torch", "numpy", "pandas"))

def test_gate_43_public_api_is_explicit(validator_module):
    assert tuple(validator_module.__all__) == ("validate_candidates", "validate_candidate")

def test_gate_44_module_is_structural_validation_contract(validator_module):
    assert "structural" in (inspect.getdoc(validator_module) or "").lower()
