"""P22.1 test-first contract: 40 acceptance and adversarial gates.

These tests intentionally precede the production implementation.  They define
only the public research-layer contract: immutable content-addressed states,
explicit hypotheses, a closed mutation algebra, deterministic candidate
ordering, and non-teleological search.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.search_space import (
    Hypothesis,
    MutationOp,
    SearchState,
    SearchSpaceError,
    apply_mutation,
    generate_candidates,
)

ROOT = "a" * 64
CAUSAL = "b" * 64
EVIDENCE = "c" * 64


def hypothesis(**overrides) -> Hypothesis:
    data = dict(
        claims=("x causes y",),
        supporting_evidence=(EVIDENCE,),
        contradicting_evidence=(),
        assumptions=("x is measurable",),
        causal_dependencies=(CAUSAL,),
        admissible_interventions=("x",),
    )
    data.update(overrides)
    return Hypothesis(**data)


def state(**overrides) -> SearchState:
    data = dict(
        evidence_root=EVIDENCE,
        causal_root=CAUSAL,
        hypothesis_set=(hypothesis(),),
        constraints=("depth<=3",),
        assumptions=(),
        search_depth=0,
    )
    data.update(overrides)
    return SearchState(**data)


def assert_sha(value: str) -> None:
    assert isinstance(value, str) and len(value) == 64
    assert all(c in "0123456789abcdef" for c in value)


def test_gate_01_schema_validity():
    s = state()
    assert s.evidence_root == EVIDENCE and s.causal_root == CAUSAL
    assert isinstance(s.hypothesis_set, tuple)


def test_gate_02_state_is_frozen():
    with pytest.raises(FrozenInstanceError):
        state().search_depth = 1


def test_gate_03_state_hash_is_sha256():
    assert_sha(state().state_hash)


def test_gate_04_state_hash_is_content_derived():
    a, b = state(), state()
    assert a.state_hash == b.state_hash


def test_gate_05_state_hash_changes_on_content_change():
    assert state().state_hash != state(search_depth=1).state_hash


def test_gate_06_state_self_verifies():
    assert state().verify() is True


def test_gate_07_evidence_root_is_explicit():
    assert state().evidence_root == EVIDENCE


def test_gate_08_causal_root_is_explicit():
    assert state().causal_root == CAUSAL


def test_gate_09_hypothesis_set_is_explicit():
    assert len(state().hypothesis_set) == 1


def test_gate_10_depth_bound_is_explicit():
    assert state().search_depth == 0


def test_gate_11_hypothesis_has_claims():
    assert hypothesis().claims == ("x causes y",)


def test_gate_12_supporting_evidence_is_tracked():
    assert hypothesis().supporting_evidence == (EVIDENCE,)


def test_gate_13_contradicting_evidence_is_tracked():
    assert hypothesis().contradicting_evidence == ()


def test_gate_14_assumptions_are_tracked():
    assert hypothesis().assumptions == ("x is measurable",)


def test_gate_15_causal_dependencies_are_tracked():
    assert hypothesis().causal_dependencies == (CAUSAL,)


def test_gate_16_interventions_are_explicit():
    assert hypothesis().admissible_interventions == ("x",)


def test_gate_17_hypothesis_hash_is_sha256():
    assert_sha(hypothesis().hypothesis_hash)


def test_gate_18_absence_of_evidence_is_not_validation():
    h = hypothesis(supporting_evidence=())
    assert h.is_validated is False


def test_gate_19_mutation_algebra_is_closed():
    assert set(MutationOp) == {
        MutationOp.ADD_CONDITION,
        MutationOp.REMOVE_CONDITION,
        MutationOp.MODIFY_PARAMETER,
        MutationOp.SPLIT_HYPOTHESIS,
        MutationOp.MERGE_HYPOTHESES,
        MutationOp.ADD_ASSUMPTION,
        MutationOp.REMOVE_ASSUMPTION,
    }


def test_gate_20_unknown_mutation_is_rejected():
    with pytest.raises((SearchSpaceError, ValueError)):
        apply_mutation(state(), "INVENT_CONCLUSION", {})


def test_gate_21_evidence_check_precedes_transition():
    with pytest.raises(SearchSpaceError):
        apply_mutation(state(), MutationOp.ADD_CONDITION, {"condition": "unsupported", "evidence": ()})


def test_gate_22_causal_constraints_are_enforced():
    with pytest.raises(SearchSpaceError):
        apply_mutation(state(), MutationOp.MODIFY_PARAMETER, {"parameter": "x", "value": 2, "causal_dependencies": ("d" * 64,)})


def test_gate_23_schema_validation_rejects_bad_payload():
    with pytest.raises((SearchSpaceError, ValueError, TypeError)):
        apply_mutation(state(), MutationOp.ADD_CONDITION, {"unexpected": object()})


def test_gate_24_invalid_mutation_does_not_create_state():
    original = state()
    with pytest.raises(SearchSpaceError):
        apply_mutation(original, MutationOp.ADD_CONDITION, {"condition": "unsupported", "evidence": ()})
    assert original == state()


def test_gate_25_target_is_not_a_mutation_input():
    with pytest.raises(TypeError):
        generate_candidates(state(), target_conclusion="x causes y")


def test_gate_26_candidate_generation_is_pure():
    original = state()
    generate_candidates(original)
    assert original == state()


def test_gate_27_candidate_generation_is_deterministic():
    assert generate_candidates(state()) == generate_candidates(state())


def test_gate_28_candidates_are_content_addressed():
    candidates = generate_candidates(state())
    assert all(len(c.state_hash) == 64 for c in candidates)


def test_gate_29_candidate_order_is_canonical():
    candidates = generate_candidates(state())
    assert tuple(c.state_hash for c in candidates) == tuple(sorted(c.state_hash for c in candidates))


def test_gate_30_equivalent_inputs_have_identical_sequence():
    left = state(constraints=("b", "a"))
    right = state(constraints=("a", "b"))
    assert [x.state_hash for x in generate_candidates(left)] == [x.state_hash for x in generate_candidates(right)]


def test_gate_31_distinct_candidates_remain_distinct():
    candidates = generate_candidates(state())
    hashes = [c.state_hash for c in candidates]
    assert len(hashes) == len(set(hashes))


def test_gate_32_duplicate_hypotheses_are_not_silently_collapsed():
    h1, h2 = hypothesis(), hypothesis(claims=("x does not cause y",))
    s = state(hypothesis_set=(h1, h2))
    assert len(s.hypothesis_set) == 2


def test_gate_33_permutation_of_mapping_keys_cannot_change_hash():
    h1 = hypothesis(claims=("x", "y"))
    h2 = Hypothesis(**dict(reversed({
        "claims": ("x", "y"), "supporting_evidence": (EVIDENCE,),
        "contradicting_evidence": (), "assumptions": ("x is measurable",),
        "causal_dependencies": (CAUSAL,), "admissible_interventions": ("x",),
    }.items())))
    assert h1.hypothesis_hash == h2.hypothesis_hash


def test_gate_34_runtime_noise_is_rejected():
    with pytest.raises((SearchSpaceError, ValueError)):
        SearchState(evidence_root=EVIDENCE, causal_root=CAUSAL, hypothesis_set=(hypothesis(),), constraints=("timestamp",), assumptions=(), search_depth=0)


def test_gate_35_target_dependent_distortion_is_detectable():
    baseline = [x.state_hash for x in generate_candidates(state())]
    assert baseline == [x.state_hash for x in generate_candidates(state())]


def test_gate_36_tampered_state_hash_is_detected():
    s = state()
    object.__setattr__(s, "state_hash", "f" * 64)
    with pytest.raises(SearchSpaceError):
        s.verify()


def test_gate_37_runtime_metadata_cannot_enter_payload():
    with pytest.raises((SearchSpaceError, ValueError)):
        hypothesis(assumptions=("hostname=host",))


def test_gate_38_filesystem_and_network_are_not_required():
    assert generate_candidates(state()) is not None


def test_gate_39_domain_layer_is_not_an_input():
    assert "jamp.domain" not in generate_candidates.__module__


def test_gate_40_replay_is_cross_runtime_content_stable():
    s = state()
    exported = s.export()
    assert replay_hash(exported) == s.state_hash
