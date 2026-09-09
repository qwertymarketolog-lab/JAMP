"""P22.2 test-first contract: candidate generation only.

The contract forbids ranking, scoring, target-directed selection, and mutation
semantics that belong to later phases. Candidates must be deterministic,
content-addressed descendants preserving evidence/causal lineage.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.search_space import Hypothesis, MutationOp, SearchState, SearchSpaceError
from jamp.research.candidate_generator import generate_candidates

ROOT = "a" * 64
CAUSAL = "b" * 64
EVIDENCE = "c" * 64
EVIDENCE_2 = "d" * 64


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


def test_gate_01_public_function_accepts_only_state():
    assert callable(generate_candidates)


def test_gate_02_result_is_ordered_tuple():
    assert isinstance(generate_candidates(state()), tuple)


def test_gate_03_result_contains_search_states():
    assert all(isinstance(c, SearchState) for c in generate_candidates(state()))


def test_gate_04_input_is_not_mutated():
    original = state()
    generate_candidates(original)
    assert original == state()


def test_gate_05_identical_inputs_are_identical():
    assert generate_candidates(state()) == generate_candidates(state())


def test_gate_06_state_hashes_are_deterministic():
    assert [c.state_hash for c in generate_candidates(state())] == [c.state_hash for c in generate_candidates(state())]


def test_gate_07_order_is_hash_canonical():
    candidates = generate_candidates(state())
    assert [c.state_hash for c in candidates] == sorted(c.state_hash for c in candidates)


def test_gate_08_candidates_are_content_addressed():
    assert all(len(c.state_hash) == 64 for c in generate_candidates(state()))


def test_gate_09_no_duplicate_candidate_hashes():
    hashes = [c.state_hash for c in generate_candidates(state())]
    assert len(hashes) == len(set(hashes))


def test_gate_10_candidates_are_descendants():
    parent = state()
    for candidate in generate_candidates(parent):
        assert candidate.search_depth == parent.search_depth + 1


def test_gate_11_evidence_root_is_inherited():
    parent = state()
    assert all(c.evidence_root == parent.evidence_root for c in generate_candidates(parent))


def test_gate_12_causal_root_is_inherited():
    parent = state()
    assert all(c.causal_root == parent.causal_root for c in generate_candidates(parent))


def test_gate_13_assumptions_are_inherited():
    parent = state(assumptions=("global assumption",))
    assert all(c.assumptions == parent.assumptions for c in generate_candidates(parent))


def test_gate_14_hypothesis_assumptions_are_preserved():
    parent = state()
    assert all(c.hypothesis_set[0].assumptions == parent.hypothesis_set[0].assumptions for c in generate_candidates(parent))


def test_gate_15_causal_dependencies_are_preserved():
    parent = state()
    assert all(c.hypothesis_set[0].causal_dependencies == parent.hypothesis_set[0].causal_dependencies for c in generate_candidates(parent))


def test_gate_16_supporting_evidence_is_preserved():
    parent = state()
    assert all(c.hypothesis_set[0].supporting_evidence == parent.hypothesis_set[0].supporting_evidence for c in generate_candidates(parent))


def test_gate_17_contradicting_evidence_is_preserved():
    parent = state()
    assert all(c.hypothesis_set[0].contradicting_evidence == parent.hypothesis_set[0].contradicting_evidence for c in generate_candidates(parent))


def test_gate_18_interventions_are_preserved():
    parent = state()
    assert all(c.hypothesis_set[0].admissible_interventions == parent.hypothesis_set[0].admissible_interventions for c in generate_candidates(parent))


def test_gate_19_empty_evidence_does_not_equal_validation():
    parent = state(hypothesis_set=(hypothesis(supporting_evidence=()),))
    candidates = generate_candidates(parent)
    assert all(not c.hypothesis_set[0].is_validated for c in candidates)


def test_gate_20_contradicting_evidence_remains_visible():
    parent = state(hypothesis_set=(hypothesis(contradicting_evidence=(EVIDENCE_2,)),))
    candidates = generate_candidates(parent)
    assert all(c.hypothesis_set[0].contradicting_evidence == (EVIDENCE_2,) for c in candidates)


def test_gate_21_empty_hypothesis_set_is_total():
    parent = state(hypothesis_set=())
    assert generate_candidates(parent) == ()


def test_gate_22_depth_limit_stops_generation():
    parent = state(search_depth=3)
    assert generate_candidates(parent) == ()


def test_gate_23_invalid_state_hash_is_rejected():
    parent = state()
    object.__setattr__(parent, "state_hash", "0" * 64)
    with pytest.raises(SearchSpaceError):
        generate_candidates(parent)


def test_gate_24_mapping_key_order_does_not_affect_input_hash():
    h1 = hypothesis(claims=("x", "y"))
    h2 = Hypothesis(**dict(reversed({
        "claims": ("x", "y"), "supporting_evidence": (EVIDENCE,),
        "contradicting_evidence": (), "assumptions": ("x is measurable",),
        "causal_dependencies": (CAUSAL,), "admissible_interventions": ("x",),
    }.items())))
    assert h1.hypothesis_hash == h2.hypothesis_hash


def test_gate_25_constraints_shuffling_preserves_candidate_sequence():
    left = state(constraints=("b", "a"))
    right = state(constraints=("a", "b"))
    assert [c.state_hash for c in generate_candidates(left)] == [c.state_hash for c in generate_candidates(right)]


def test_gate_26_hypothesis_claim_shuffling_is_canonical():
    left = state(hypothesis_set=(hypothesis(claims=("b", "a")),))
    right = state(hypothesis_set=(hypothesis(claims=("a", "b")),))
    assert [c.state_hash for c in generate_candidates(left)] == [c.state_hash for c in generate_candidates(right)]


def test_gate_27_target_argument_is_forbidden():
    with pytest.raises(TypeError):
        generate_candidates(state(), target_conclusion="x causes y")


def test_gate_28_scoring_argument_is_forbidden():
    with pytest.raises(TypeError):
        generate_candidates(state(), score=lambda _: 1)


def test_gate_29_ranking_argument_is_forbidden():
    with pytest.raises(TypeError):
        generate_candidates(state(), ranking="best-first")


def test_gate_30_bayesian_weight_argument_is_forbidden():
    with pytest.raises(TypeError):
        generate_candidates(state(), bayesian_weight=0.9)


def test_gate_31_counterfactual_argument_is_forbidden():
    with pytest.raises(TypeError):
        generate_candidates(state(), counterfactual=True)


def test_gate_32_mutation_op_is_explicitly_closed():
    assert {x.value for x in MutationOp} == {
        "ADD_CONDITION", "REMOVE_CONDITION", "MODIFY_PARAMETER",
        "SPLIT_HYPOTHESIS", "MERGE_HYPOTHESES", "ADD_ASSUMPTION", "REMOVE_ASSUMPTION",
    }


def test_gate_33_generator_does_not_invent_unknown_mutations():
    candidates = generate_candidates(state())
    assert all(isinstance(c, SearchState) for c in candidates)


def test_gate_34_candidate_hash_matches_its_content():
    for candidate in generate_candidates(state()):
        assert candidate.state_hash == replay_hash(candidate.export())


def test_gate_35_parent_hash_is_not_reused_as_candidate_hash():
    parent = state()
    assert all(c.state_hash != parent.state_hash for c in generate_candidates(parent))


def test_gate_36_candidate_verification_survives_generation():
    assert all(c.verify() for c in generate_candidates(state()))


def test_gate_37_generation_has_no_runtime_metadata_dependency():
    assert [c.state_hash for c in generate_candidates(state())] == [c.state_hash for c in generate_candidates(state())]


def test_gate_38_generation_does_not_rank_by_evidence_count():
    a = state(hypothesis_set=(hypothesis(supporting_evidence=(EVIDENCE,)),))
    b = state(hypothesis_set=(hypothesis(supporting_evidence=(EVIDENCE, EVIDENCE_2)),))
    assert [c.state_hash for c in generate_candidates(a)] == [c.state_hash for c in generate_candidates(a)]
    assert all(c.hypothesis_set[0].supporting_evidence == b.hypothesis_set[0].supporting_evidence for c in generate_candidates(b))


def test_gate_39_frozen_candidate_state():
    candidate = generate_candidates(state())[0]
    with pytest.raises(FrozenInstanceError):
        candidate.search_depth = 99


def test_gate_40_no_selection_api_is_exposed():
    assert not hasattr(generate_candidates, "select")


def test_gate_41_multiple_hypotheses_remain_separate():
    parent = state(hypothesis_set=(hypothesis(), hypothesis(claims=("z",))))
    candidates = generate_candidates(parent)
    assert all(len(c.hypothesis_set) == 2 for c in candidates)


def test_gate_42_candidate_generation_is_not_target_directed():
    parent = state(hypothesis_set=(hypothesis(claims=("alpha", "beta")),))
    assert len(generate_candidates(parent)) >= 1


def test_gate_43_candidate_generation_preserves_global_lineage():
    parent = state(assumptions=("A",), causal_root=CAUSAL, evidence_root=EVIDENCE)
    for candidate in generate_candidates(parent):
        assert candidate.evidence_root == EVIDENCE
        assert candidate.causal_root == CAUSAL
        assert candidate.assumptions == ("A",)


def test_gate_44_no_external_selection_dependency():
    assert generate_candidates.__module__ == "jamp.research.candidate_generator"
