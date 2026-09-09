"""P22.4 executable contract: deterministic evidence-grounded evaluation.

This is intentionally a Test-First contract.  The production evaluation module
is expected to be introduced only after these gates exist.  The contract treats
an immutable SearchState as the P22.3 StructuralCandidate representation until
a dedicated immutable candidate type is introduced.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import os
import random
import socket
import subprocess
import uuid
from collections.abc import Mapping

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.search_space import Hypothesis, SearchSpaceError, SearchState

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def make_candidate(*, claims=("x=1",), depth=0, constraints=(), assumptions=("A",),
                   evidence_root=SHA_A, causal_root=SHA_B, support=(SHA_C,),
                   contradicting=(), causal=(SHA_B,), interventions=("do(x)",)):
    h = Hypothesis(
        tuple(claims), tuple(support), tuple(contradicting), tuple(assumptions),
        tuple(causal), tuple(interventions)
    )
    return SearchState(
        evidence_root, causal_root, (h,), tuple(constraints), tuple(assumptions), depth
    )


@pytest.fixture
def evaluation_module():
    try:
        from jamp.research import evaluation
    except ImportError as exc:
        pytest.fail(f"P22.4 production module is required: {exc}")
    return evaluation


def test_gate_01_module_exists(evaluation_module):
    assert evaluation_module


def test_gate_02_public_evaluator_exists(evaluation_module):
    assert callable(evaluation_module.evaluate_candidate)


def test_gate_03_public_metrics_type_exists(evaluation_module):
    assert hasattr(evaluation_module, "EvaluationMetrics")


def test_gate_04_evaluator_signature_is_candidate_only(evaluation_module):
    assert list(inspect.signature(evaluation_module.evaluate_candidate).parameters) == ["candidate"]


def test_gate_05_candidate_is_search_state_compatible(evaluation_module):
    result = evaluation_module.evaluate_candidate(make_candidate())
    assert result is not None


def test_gate_06_result_is_metrics_type(evaluation_module):
    result = evaluation_module.evaluate_candidate(make_candidate())
    assert isinstance(result, evaluation_module.EvaluationMetrics)


def test_gate_07_metrics_is_frozen_dataclass(evaluation_module):
    assert dataclasses.is_dataclass(evaluation_module.EvaluationMetrics)
    assert evaluation_module.EvaluationMetrics.__dataclass_params__.frozen


def test_gate_08_state_hash_is_anchored(evaluation_module):
    candidate = make_candidate()
    result = evaluation_module.evaluate_candidate(candidate)
    assert result.state_hash == candidate.state_hash


def test_gate_09_evidence_root_is_anchored(evaluation_module):
    candidate = make_candidate()
    result = evaluation_module.evaluate_candidate(candidate)
    assert result.evidence_root == candidate.evidence_root


def test_gate_10_causal_root_is_anchored(evaluation_module):
    candidate = make_candidate()
    result = evaluation_module.evaluate_candidate(candidate)
    assert result.causal_root == candidate.causal_root


def test_gate_11_state_hash_matches_canonical_export(evaluation_module):
    candidate = make_candidate()
    assert candidate.state_hash == replay_hash(candidate.export())
    assert evaluation_module.evaluate_candidate(candidate).state_hash == replay_hash(candidate.export())


def test_gate_12_score_is_present(evaluation_module):
    assert "score" in {field.name for field in dataclasses.fields(evaluation_module.EvaluationMetrics)}


def test_gate_13_score_is_mapping_not_scalar_rank(evaluation_module):
    result = evaluation_module.evaluate_candidate(make_candidate())
    assert isinstance(result.score, Mapping)


def test_gate_14_score_contains_only_raw_empirical_metrics(evaluation_module):
    result = evaluation_module.evaluate_candidate(make_candidate())
    assert set(result.score) == {
        "claim_count",
        "supporting_evidence_count",
        "contradicting_evidence_count",
        "causal_dependency_count",
        "assumption_count",
        "admissible_intervention_count",
        "search_depth",
    }


def test_gate_15_claim_count_is_exact(evaluation_module):
    candidate = make_candidate(claims=("x=1", "y=2"))
    assert evaluation_module.evaluate_candidate(candidate).score["claim_count"] == 2


def test_gate_16_support_count_is_exact(evaluation_module):
    candidate = make_candidate(support=(SHA_A, SHA_C))
    assert evaluation_module.evaluate_candidate(candidate).score["supporting_evidence_count"] == 2


def test_gate_17_contradiction_count_is_exact(evaluation_module):
    candidate = make_candidate(contradicting=(SHA_B,))
    assert evaluation_module.evaluate_candidate(candidate).score["contradicting_evidence_count"] == 1


def test_gate_18_causal_count_is_exact(evaluation_module):
    candidate = make_candidate(causal=(SHA_A, SHA_B))
    assert evaluation_module.evaluate_candidate(candidate).score["causal_dependency_count"] == 2


def test_gate_19_assumption_count_is_exact(evaluation_module):
    candidate = make_candidate(assumptions=("A", "B"))
    assert evaluation_module.evaluate_candidate(candidate).score["assumption_count"] == 2


def test_gate_20_intervention_count_is_exact(evaluation_module):
    candidate = make_candidate(interventions=("do(x)", "do(y)"))
    assert evaluation_module.evaluate_candidate(candidate).score["admissible_intervention_count"] == 2


def test_gate_21_depth_is_exact(evaluation_module):
    candidate = make_candidate(depth=3)
    assert evaluation_module.evaluate_candidate(candidate).score["search_depth"] == 3


def test_gate_22_no_contradiction_normalization(evaluation_module):
    candidate = make_candidate(contradicting=(SHA_A, SHA_B))
    assert evaluation_module.evaluate_candidate(candidate).score["contradicting_evidence_count"] == 2


def test_gate_23_empty_evidence_is_zero(evaluation_module):
    candidate = make_candidate(support=(), contradicting=())
    result = evaluation_module.evaluate_candidate(candidate)
    assert result.score["supporting_evidence_count"] == 0
    assert result.score["contradicting_evidence_count"] == 0


def test_gate_24_repeated_evaluation_is_identical(evaluation_module):
    candidate = make_candidate()
    assert evaluation_module.evaluate_candidate(candidate) == evaluation_module.evaluate_candidate(candidate)


def test_gate_25_evaluation_does_not_mutate_candidate(evaluation_module):
    candidate = make_candidate()
    snapshot = candidate.export()
    evaluation_module.evaluate_candidate(candidate)
    assert candidate.export() == snapshot


def test_gate_26_result_score_is_immutable(evaluation_module):
    result = evaluation_module.evaluate_candidate(make_candidate())
    with pytest.raises((TypeError, AttributeError)):
        result.score["claim_count"] = 999


def test_gate_27_result_field_assignment_is_forbidden(evaluation_module):
    result = evaluation_module.evaluate_candidate(make_candidate())
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.state_hash = "0" * 64


def test_gate_28_equivalent_candidates_produce_equal_results(evaluation_module):
    a = make_candidate(claims=("b", "a"), assumptions=("B", "A"))
    b = make_candidate(claims=("a", "b"), assumptions=("A", "B"))
    assert evaluation_module.evaluate_candidate(a) == evaluation_module.evaluate_candidate(b)


def test_gate_29_evidence_root_change_changes_anchor(evaluation_module):
    a = evaluation_module.evaluate_candidate(make_candidate(evidence_root=SHA_A))
    b = evaluation_module.evaluate_candidate(make_candidate(evidence_root=SHA_B))
    assert a.evidence_root != b.evidence_root


def test_gate_30_causal_root_change_changes_anchor(evaluation_module):
    a = evaluation_module.evaluate_candidate(make_candidate(causal_root=SHA_A, causal=(SHA_A,)))
    b = evaluation_module.evaluate_candidate(make_candidate(causal_root=SHA_B, causal=(SHA_B,)))
    assert a.causal_root != b.causal_root


def test_gate_31_invalid_state_hash_is_rejected(evaluation_module):
    candidate = make_candidate()
    object.__setattr__(candidate, "state_hash", "0" * 64)
    with pytest.raises(SearchSpaceError):
        evaluation_module.evaluate_candidate(candidate)


def test_gate_32_invalid_candidate_type_is_rejected(evaluation_module):
    with pytest.raises((TypeError, SearchSpaceError)):
        evaluation_module.evaluate_candidate(object())


def test_gate_33_none_candidate_is_rejected(evaluation_module):
    with pytest.raises((TypeError, SearchSpaceError)):
        evaluation_module.evaluate_candidate(None)


def test_gate_34_no_selection_api(evaluation_module):
    names = set(dir(evaluation_module))
    assert not {"select", "select_candidate", "select_candidates"} & names


def test_gate_35_no_ranking_api(evaluation_module):
    names = set(dir(evaluation_module))
    assert not {"rank", "rank_candidate", "rank_candidates", "sort_candidates"} & names


def test_gate_36_no_threshold_filter_api(evaluation_module):
    names = set(dir(evaluation_module))
    assert not {"filter", "filter_candidates", "threshold", "apply_threshold"} & names


def test_gate_37_no_heuristic_api(evaluation_module):
    names = set(dir(evaluation_module))
    assert not {"heuristic", "heuristic_score", "estimate", "approximate"} & names


def test_gate_38_no_teleological_api(evaluation_module):
    names = set(dir(evaluation_module))
    assert not {"goal", "objective", "utility", "fitness"} & names


def test_gate_39_no_bayesian_or_speculative_api(evaluation_module):
    names = set(dir(evaluation_module))
    assert not {"prior", "posterior", "bayesian", "probability", "prediction"} & names


def test_gate_40_no_random_runtime_dependency(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert "random" not in source
    assert "secrets" not in source


def test_gate_41_no_clock_runtime_dependency(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert not any(token in source for token in ("datetime", "time.time", "time_ns", "perf_counter"))


def test_gate_42_no_host_runtime_dependency(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert not any(token in source for token in ("hostname", "gethostname", "socket."))


def test_gate_43_no_process_runtime_dependency(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert not any(token in source for token in ("subprocess", "popen", "system("))


def test_gate_44_no_uuid_runtime_dependency(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert "uuid" not in source


def test_gate_45_no_environment_reads(evaluation_module):
    source = inspect.getsource(evaluation_module)
    assert not any(token in source for token in ("os.environ", "os.getenv", "getenv("))


def test_gate_46_no_external_numeric_stack(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert not any(token in source for token in ("numpy", "pandas", "torch", "sklearn"))


def test_gate_47_no_imported_selection_framework(evaluation_module):
    tree = ast.parse(inspect.getsource(evaluation_module))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not {"numpy", "pandas", "torch", "sklearn"} & imported


def test_gate_48_public_api_is_explicit(evaluation_module):
    assert tuple(evaluation_module.__all__) == ("EvaluationMetrics", "evaluate_candidate")


def test_gate_49_no_mutating_collection_operations(evaluation_module):
    source = inspect.getsource(evaluation_module)
    assert not any(token in source for token in (".sort(", ".append(", ".extend(", ".pop(", ".remove("))


def test_gate_50_no_candidate_ordering_logic(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert not any(token in source for token in ("sorted(", "min(", "max(", "key=lambda"))


def test_gate_51_no_selection_thresholds(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert not any(token in source for token in ("if score", "if metric", "> threshold", "< threshold", ">= threshold", "<= threshold"))


def test_gate_52_only_cryptographic_candidate_identity_is_external_anchor(evaluation_module):
    source = inspect.getsource(evaluation_module).lower()
    assert "state_hash" in source
    assert "evidence_root" in source
    assert "causal_root" in source
    assert not any(token in source for token in ("id(candidate)", "repr(candidate)", "str(candidate)"))


def test_gate_53_diagnostic_contract_has_no_test_side_effect_imports(evaluation_module):
    assert random.__name__ == "random"
    assert socket.__name__ == "socket"
    assert subprocess.__name__ == "subprocess"
    assert uuid.__name__ == "uuid"
    assert os.__name__ == "os"
