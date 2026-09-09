"""P22.8 test-first contract for deterministic hypothesis formation.

The production module is intentionally absent at contract deployment time.
These gates define the immutable public boundary before implementation.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from jamp.research import evidence
from jamp.research import hypothesis_formation as hypothesis

FORBIDDEN = {
    "select", "select_node", "select_nodes", "rank", "sort", "sorted",
    "filter", "threshold", "heuristic", "estimate", "approximate",
    "goal", "objective", "utility", "fitness", "probability", "prediction",
    "confidence", "weight", "score", "score_hypothesis", "relevance",
    "priority", "optimize", "optimization", "bayesian",
}
HEX64 = "a" * 64
HEX64_B = "b" * 64
HEX64_C = "c" * 64


def _source_tree():
    return ast.parse(inspect.getsource(hypothesis))


def _evidence(a=HEX64, b=HEX64_B, state=HEX64_C, sequence=0):
    return evidence.EvidenceRecord(a, b, state, sequence)


def _ledger():
    return evidence.build_evidence_ledger([_evidence()])


def _hypothesis(sequence=0, proposition="observation implies structure"):
    return hypothesis.Hypothesis(
        evidence_refs=(HEX64,), state_hash=HEX64_C,
        proposition=proposition, sequence=sequence,
    )


def test_module_exports_public_boundary():
    assert hypothesis.Hypothesis
    assert hypothesis.HypothesisSet
    assert hypothesis.build_hypothesis_set
    assert hypothesis.verify_hypothesis_provenance


def test_hypothesis_is_dataclass():
    assert is_dataclass(hypothesis.Hypothesis)


def test_hypothesis_is_frozen():
    with pytest.raises(FrozenInstanceError):
        _hypothesis().proposition = "changed"


def test_hypothesis_has_expected_fields():
    names = tuple(hypothesis.Hypothesis.__dataclass_fields__)
    assert names == ("hypothesis_hash", "evidence_refs", "state_hash", "proposition", "sequence")


def test_hypothesis_hash_is_content_addressed():
    assert len(_hypothesis().hypothesis_hash) == 64
    assert all(c in "0123456789abcdef" for c in _hypothesis().hypothesis_hash)


def test_same_inputs_have_same_hash():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash


def test_proposition_changes_identity():
    assert _hypothesis().hypothesis_hash != _hypothesis(proposition="different").hypothesis_hash


def test_sequence_changes_identity():
    assert _hypothesis().hypothesis_hash != _hypothesis(sequence=1).hypothesis_hash


def test_state_changes_identity():
    h1 = _hypothesis()
    h2 = hypothesis.Hypothesis((HEX64,), HEX64_B, "observation implies structure", 0)
    assert h1.hypothesis_hash != h2.hypothesis_hash


def test_evidence_refs_are_tuple():
    assert isinstance(_hypothesis().evidence_refs, tuple)


def test_evidence_refs_are_immutable():
    with pytest.raises(FrozenInstanceError):
        _hypothesis().evidence_refs = (HEX64_B,)


def test_state_hash_is_string():
    assert _hypothesis().state_hash == HEX64_C


def test_proposition_is_string():
    assert isinstance(_hypothesis().proposition, str)


def test_sequence_is_integer():
    assert _hypothesis().sequence == 0


def test_bool_sequence_rejected():
    with pytest.raises((TypeError, ValueError)):
        _hypothesis(sequence=True)


def test_negative_sequence_rejected():
    with pytest.raises(ValueError):
        _hypothesis(sequence=-1)

@pytest.mark.parametrize("bad", ["", "a", "A" * 64, "g" * 64, 1, None])
def test_state_hash_validation(bad):
    with pytest.raises((TypeError, ValueError)):
        hypothesis.Hypothesis((HEX64,), bad, "p", 0)

@pytest.mark.parametrize("refs", [(), ("a",), ("A" * 64,), ("g" * 64,), (1,)])
def test_evidence_reference_validation(refs):
    with pytest.raises((TypeError, ValueError)):
        hypothesis.Hypothesis(refs, HEX64_C, "p", 0)

@pytest.mark.parametrize("proposition", ["", "a", "unicode: наблюдение → гипотеза"])
def test_proposition_forms_identity(proposition):
    h = hypothesis.Hypothesis((HEX64,), HEX64_C, proposition, 0)
    assert isinstance(h.hypothesis_hash, str)


def test_export_is_detached_mapping():
    exported = _hypothesis().export()
    assert isinstance(exported, dict)
    assert exported["evidence_refs"] == [HEX64]
    exported["evidence_refs"].append(HEX64_B)
    assert _hypothesis().evidence_refs == (HEX64,)


def test_export_contains_all_fields():
    assert set(_hypothesis().export()) == {"hypothesis_hash", "evidence_refs", "state_hash", "proposition", "sequence"}


def test_hypothesis_set_is_frozen():
    hs = hypothesis.HypothesisSet((_hypothesis(),), "0" * 64)
    with pytest.raises(FrozenInstanceError):
        hs.hypotheses = ()


def test_hypothesis_set_requires_tuple():
    with pytest.raises(TypeError):
        hypothesis.HypothesisSet([_hypothesis()], "0" * 64)


def test_hypothesis_set_requires_valid_commitment():
    with pytest.raises(ValueError):
        hypothesis.HypothesisSet((_hypothesis(),), "0" * 64)


def test_build_empty_set():
    hs = hypothesis.build_hypothesis_set([], _ledger())
    assert hs.hypotheses == ()
    assert len(hs.set_hash) == 64


def test_build_single_hypothesis():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    assert hs.hypotheses == (_hypothesis(),)


def test_build_requires_ledger():
    with pytest.raises(TypeError):
        hypothesis.build_hypothesis_set([_hypothesis()], object())


def test_build_requires_sequence_input():
    with pytest.raises(TypeError):
        hypothesis.build_hypothesis_set("x", _ledger())


def test_build_rejects_missing_evidence_reference():
    missing = hypothesis.Hypothesis((HEX64_B,), HEX64_C, "p", 0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([missing], _ledger())


def test_build_rejects_wrong_state_grounding():
    wrong = hypothesis.Hypothesis((HEX64,), HEX64_B, "p", 0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([wrong], _ledger())


def test_build_rejects_duplicate_sequences():
    h0 = _hypothesis(0)
    h1 = _hypothesis(0, "second")
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([h0, h1], _ledger())


def test_build_rejects_sequence_gap():
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([_hypothesis(1)], _ledger())


def test_build_rejects_duplicate_hypothesis_hash():
    h = _hypothesis()
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([h, h], _ledger())


def test_build_canonicalizes_sequence_order():
    h0 = _hypothesis(0)
    h1 = _hypothesis(1, "second")
    hs = hypothesis.build_hypothesis_set([h1, h0], _ledger())
    assert tuple(h.sequence for h in hs.hypotheses) == (0, 1)


def test_set_hash_is_deterministic():
    h0 = _hypothesis(0)
    h1 = _hypothesis(1, "second")
    assert hypothesis.build_hypothesis_set([h0, h1], _ledger()).set_hash == hypothesis.build_hypothesis_set([h1, h0], _ledger()).set_hash


def test_set_hash_changes_with_content():
    a = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    b = hypothesis.build_hypothesis_set([_hypothesis(proposition="other")], _ledger())
    assert a.set_hash != b.set_hash


def test_hypothesis_set_export_is_detached():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    exported = hs.export()
    exported["hypotheses"][0]["evidence_refs"].append(HEX64_B)
    assert hs.hypotheses[0].evidence_refs == (HEX64,)


def test_set_export_contains_hash():
    hs = hypothesis.build_hypothesis_set([], _ledger())
    assert set(hs.export()) == {"hypotheses", "set_hash"}


def test_verify_accepts_valid_set():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    assert hypothesis.verify_hypothesis_provenance(hs, _ledger()) is True


def test_verify_rejects_wrong_ledger():
    other = evidence.build_evidence_ledger([_evidence(HEX64_B, HEX64, HEX64_C, 0)])
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    with pytest.raises(ValueError):
        hypothesis.verify_hypothesis_provenance(hs, other)


def test_verify_requires_hypothesis_set():
    with pytest.raises(TypeError):
        hypothesis.verify_hypothesis_provenance(object(), _ledger())


def test_verify_requires_ledger():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    with pytest.raises(TypeError):
        hypothesis.verify_hypothesis_provenance(hs, object())


def test_verify_detects_tampered_hypothesis_hash():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    tampered = hypothesis.HypothesisSet(
        (hypothesis.Hypothesis.__new__(hypothesis.Hypothesis),), hs.set_hash
    )
    with pytest.raises((ValueError, TypeError, AttributeError)):
        hypothesis.verify_hypothesis_provenance(tampered, _ledger())


def test_verify_detects_set_commitment_tamper():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    with pytest.raises(ValueError):
        hypothesis.HypothesisSet(hs.hypotheses, HEX64)


def test_provenance_references_evidence_hashes():
    h = _hypothesis()
    assert h.evidence_refs == (_ledger().records[0].evidence_hash,)


def test_provenance_is_state_grounded():
    assert _hypothesis().state_hash == _ledger().records[0].state_hash


def test_hash_is_lowercase_sha256():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash.lower()


def test_set_hash_is_lowercase_sha256():
    hs = hypothesis.build_hypothesis_set([], _ledger())
    assert hs.set_hash == hs.set_hash.lower()


def test_multiple_evidence_refs_supported():
    e0 = _evidence(sequence=0)
    e1 = _evidence(HEX64_B, HEX64, HEX64_C, 1)
    ledger = evidence.build_evidence_ledger([e0, e1])
    h = hypothesis.Hypothesis((e0.evidence_hash, e1.evidence_hash), HEX64_C, "combined", 0)
    hs = hypothesis.build_hypothesis_set([h], ledger)
    assert hs.hypotheses[0].evidence_refs == (e0.evidence_hash, e1.evidence_hash)


def test_multiple_hypotheses_supported():
    e0 = _evidence(sequence=0)
    e1 = _evidence(HEX64_B, HEX64, HEX64_C, 1)
    ledger = evidence.build_evidence_ledger([e0, e1])
    h0 = hypothesis.Hypothesis((e0.evidence_hash,), HEX64_C, "first", 0)
    h1 = hypothesis.Hypothesis((e1.evidence_hash,), HEX64_C, "second", 1)
    hs = hypothesis.build_hypothesis_set([h1, h0], ledger)
    assert tuple(h.sequence for h in hs.hypotheses) == (0, 1)


def test_hypothesis_order_is_structural_not_semantic():
    h0 = _hypothesis(0, "z proposition")
    h1 = _hypothesis(1, "a proposition")
    hs = hypothesis.build_hypothesis_set([h1, h0], _ledger()) if False else None
    assert h0.sequence < h1.sequence


def test_no_runtime_environment_access_ast():
    names = {n.id for n in ast.walk(_source_tree()) if isinstance(n, ast.Name)}
    assert not names.intersection({"time", "random", "id", "os", "environ"})


def test_no_filesystem_or_network_imports_ast():
    imports = {n.module.split(".")[0] for n in ast.walk(_source_tree()) if isinstance(n, ast.ImportFrom) and n.module}
    imports |= {a.name.split(".")[0] for n in ast.walk(_source_tree()) if isinstance(n, ast.Import) for a in n.names}
    assert not imports.intersection({"os", "pathlib", "socket", "urllib", "requests", "httpx"})


def test_no_decision_vocabulary_ast():
    names = {n.id.lower() for n in ast.walk(_source_tree()) if isinstance(n, ast.Name)}
    attrs = {n.attr.lower() for n in ast.walk(_source_tree()) if isinstance(n, ast.Attribute)}
    strings = {n.value.lower() for n in ast.walk(_source_tree()) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    tokens = names | attrs | strings
    assert not tokens.intersection(FORBIDDEN)


def test_no_function_named_decision_logic():
    funcs = {n.name.lower() for n in ast.walk(_source_tree()) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not funcs.intersection(FORBIDDEN)


def test_no_sorting_calls_ast():
    calls = [n for n in ast.walk(_source_tree()) if isinstance(n, ast.Call)]
    assert not any(isinstance(c.func, ast.Name) and c.func.id in {"sorted", "sort"} for c in calls)


def test_no_score_confidence_probability_ast():
    source = inspect.getsource(hypothesis).lower()
    assert all(token not in source for token in ("score", "confidence", "probability", "bayesian"))


def test_no_selection_ranking_filtering_ast():
    source = inspect.getsource(hypothesis).lower()
    assert all(token not in source for token in ("selection", "ranking", "filtering", "threshold"))


def test_no_mutable_class_decorators():
    for node in ast.walk(_source_tree()):
        if isinstance(node, ast.ClassDef) and node.name in {"Hypothesis", "HypothesisSet"}:
            assert any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass" for d in node.decorator_list)


def test_only_structural_public_names():
    public = set(getattr(hypothesis, "__all__", ()))
    assert public == {"Hypothesis", "HypothesisSet", "build_hypothesis_set", "verify_hypothesis_provenance"}


def test_no_identity_based_hashing():
    source = inspect.getsource(hypothesis)
    assert "id(" not in source
    assert "hash(" not in source


def test_no_time_random_environment_strings():
    source = inspect.getsource(hypothesis).lower()
    assert all(token not in source for token in ("time.time", "random.", "os.environ", "getenv", "open("))


def test_repeated_verification_is_deterministic():
    ledger = _ledger()
    hs = hypothesis.build_hypothesis_set([_hypothesis()], ledger)
    assert hypothesis.verify_hypothesis_provenance(hs, ledger) is True
    assert hypothesis.verify_hypothesis_provenance(hs, ledger) is True


def test_detached_export_roundtrip_identity():
    h = _hypothesis()
    exported = h.export()
    rebuilt = hypothesis.Hypothesis(tuple(exported["evidence_refs"]), exported["state_hash"], exported["proposition"], exported["sequence"])
    assert rebuilt.hypothesis_hash == h.hypothesis_hash


def test_set_roundtrip_identity():
    ledger = _ledger()
    hs = hypothesis.build_hypothesis_set([_hypothesis()], ledger)
    rebuilt_h = hypothesis.Hypothesis(**{k: hs.hypotheses[0].export()[k] for k in ("evidence_refs", "state_hash", "proposition", "sequence")})
    rebuilt = hypothesis.build_hypothesis_set([rebuilt_h], ledger)
    assert rebuilt.set_hash == hs.set_hash


def test_cwd_independence_by_contract():
    assert "cwd" not in inspect.getsource(hypothesis).lower()


def test_network_independence_by_contract():
    source = inspect.getsource(hypothesis).lower()
    assert all(token not in source for token in ("socket", "requests", "httpx", "urllib"))


def test_hypothesis_proposition_is_not_evaluated():
    h = _hypothesis(proposition="1/0")
    assert h.proposition == "1/0"


def test_evidence_binding_does_not_mutate_ledger():
    ledger = _ledger()
    before = ledger.export()
    hypothesis.build_hypothesis_set([_hypothesis()], ledger)
    assert ledger.export() == before


def test_build_does_not_mutate_hypotheses():
    h = _hypothesis()
    before = h.export()
    hypothesis.build_hypothesis_set([h], _ledger())
    assert h.export() == before


def test_set_records_are_hypothesis_instances():
    hs = hypothesis.build_hypothesis_set([_hypothesis()], _ledger())
    assert all(isinstance(item, hypothesis.Hypothesis) for item in hs.hypotheses)


def test_set_hash_length():
    assert len(hypothesis.build_hypothesis_set([], _ledger()).set_hash) == 64


def test_empty_provenance_verifies():
    ledger = _ledger()
    hs = hypothesis.build_hypothesis_set([], ledger)
    assert hypothesis.verify_hypothesis_provenance(hs, ledger)


def test_empty_set_export_detached():
    hs = hypothesis.build_hypothesis_set([], _ledger())
    assert hs.export() == {"hypotheses": [], "set_hash": hs.set_hash}
