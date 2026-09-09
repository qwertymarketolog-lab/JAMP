"""P22.8 contract: deterministic, immutable, provenance-preserving hypothesis formation."""
from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from jamp.research import canonical, evidence
from jamp.research import hypothesis_formation as hypothesis

P = "observation implies structure"
STATE = "c" * 64
PAYLOAD = "a" * 64
SOURCE = "b" * 64


def _evidence(payload=PAYLOAD, source=SOURCE, state=STATE, sequence=0):
    return evidence.EvidenceRecord(payload, source, state, sequence)


def _ledger(records=None):
    return evidence.build_evidence_ledger([_evidence()] if records is None else records)


def _hypothesis(record=None, proposition=P, sequence=0):
    record = _evidence(sequence=sequence) if record is None else record
    return hypothesis.Hypothesis((record.evidence_hash,), record.state_hash, proposition, sequence)


def _valid_set():
    record = _evidence()
    return hypothesis.build_hypothesis_set([_hypothesis(record)], _ledger([record]))


def _tree():
    return ast.parse(inspect.getsource(hypothesis))


def test_public_boundary():
    assert set(hypothesis.__all__) == {"Hypothesis", "HypothesisSet", "build_hypothesis_set", "verify_hypothesis_provenance"}


def test_hypothesis_dataclass():
    assert is_dataclass(hypothesis.Hypothesis)


def test_hypothesis_frozen():
    with pytest.raises(FrozenInstanceError):
        _hypothesis().proposition = "changed"


def test_hypothesis_fields():
    assert tuple(hypothesis.Hypothesis.__dataclass_fields__) == ("hypothesis_hash", "evidence_refs", "state_hash", "proposition", "sequence")


def test_hash_is_sha256_hex():
    value = _hypothesis().hypothesis_hash
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def test_hash_reproducible():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash

@pytest.mark.parametrize("field", ["proposition", "sequence"])
def test_content_changes_identity(field):
    first = _hypothesis()
    second = _hypothesis(proposition="different", sequence=0) if field == "proposition" else _hypothesis(sequence=1, record=_evidence(sequence=1))
    assert first.hypothesis_hash != second.hypothesis_hash


def test_state_changes_identity():
    r0 = _evidence()
    r1 = _evidence(state="d" * 64)
    assert _hypothesis(r0).hypothesis_hash != _hypothesis(r1).hypothesis_hash


def test_refs_tuple():
    assert isinstance(_hypothesis().evidence_refs, tuple)


def test_refs_immutable():
    with pytest.raises(FrozenInstanceError):
        _hypothesis().evidence_refs = ()


def test_state_string():
    assert _hypothesis().state_hash == STATE


def test_proposition_string():
    assert isinstance(_hypothesis().proposition, str)


def test_sequence_integer():
    assert isinstance(_hypothesis().sequence, int)

@pytest.mark.parametrize("bad", [True, -1, "0", 1.5, None])
def test_sequence_validation(bad):
    with pytest.raises((TypeError, ValueError)):
        hypothesis.Hypothesis(("0" * 64,), STATE, P, bad)

@pytest.mark.parametrize("bad", ["", "x", "A" * 64, "g" * 64, None, 1])
def test_state_hash_validation(bad):
    with pytest.raises((TypeError, ValueError)):
        hypothesis.Hypothesis(("0" * 64,), bad, P, 0)

@pytest.mark.parametrize("bad", [(), ("x",), ("A" * 64,), ("g" * 64,), (1,)])
def test_evidence_ref_validation(bad):
    with pytest.raises((TypeError, ValueError)):
        hypothesis.Hypothesis(bad, STATE, P, 0)

@pytest.mark.parametrize("proposition", ["", "a", "unicode: наблюдение → гипотеза"])
def test_proposition_forms(proposition):
    assert isinstance(hypothesis.Hypothesis(("0" * 64,), STATE, proposition, 0).hypothesis_hash, str)


def test_export_is_detached():
    exported = _hypothesis().export()
    exported["evidence_refs"].append("d" * 64)
    assert len(_hypothesis().evidence_refs) == 1


def test_export_fields():
    assert set(_hypothesis().export()) == {"hypothesis_hash", "evidence_refs", "state_hash", "proposition", "sequence"}


def test_set_dataclass():
    assert is_dataclass(hypothesis.HypothesisSet)


def test_set_frozen():
    hs = _valid_set()
    with pytest.raises(FrozenInstanceError):
        hs.hypotheses = ()


def test_set_requires_tuple():
    with pytest.raises(TypeError):
        hypothesis.HypothesisSet([_hypothesis()], "0" * 64)


def test_set_requires_valid_commitment():
    hs = _valid_set()
    with pytest.raises(ValueError):
        hypothesis.HypothesisSet(hs.hypotheses, "0" * 64)


def test_set_hash_hex():
    value = _valid_set().set_hash
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def test_empty_build():
    hs = hypothesis.build_hypothesis_set([], _ledger())
    assert hs.hypotheses == ()
    assert hypothesis.verify_hypothesis_provenance(hs, _ledger()) is True


def test_single_build():
    hs = _valid_set()
    assert len(hs.hypotheses) == 1


def test_build_requires_ledger():
    with pytest.raises(TypeError):
        hypothesis.build_hypothesis_set([], object())


def test_build_rejects_string_sequence():
    with pytest.raises(TypeError):
        hypothesis.build_hypothesis_set("x", _ledger())


def test_build_rejects_missing_evidence():
    missing = hypothesis.Hypothesis(("d" * 64,), STATE, P, 0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([missing], _ledger())


def test_build_rejects_wrong_state():
    record = _evidence()
    wrong = hypothesis.Hypothesis((record.evidence_hash,), "d" * 64, P, 0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([wrong], _ledger([record]))


def test_build_rejects_duplicate_sequences():
    r0 = _evidence()
    h0 = _hypothesis(r0, sequence=0)
    h1 = _hypothesis(r0, proposition="second", sequence=0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([h0, h1], _ledger([r0]))


def test_build_rejects_sequence_gap():
    r1 = _evidence(sequence=1)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([_hypothesis(r1, sequence=1)], _ledger([r1]))


def test_build_rejects_duplicate_hypothesis():
    r0 = _evidence()
    h = _hypothesis(r0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([h, h], _ledger([r0]))


def test_build_preserves_sequence_order_structurally():
    r0 = _evidence(sequence=0)
    r1 = _evidence(source="d" * 64, sequence=1)
    h0 = _hypothesis(r0, sequence=0)
    h1 = _hypothesis(r1, proposition="second", sequence=1)
    hs = hypothesis.build_hypothesis_set([h1, h0], _ledger([r0, r1]))
    assert tuple(h.sequence for h in hs.hypotheses) == (0, 1)


def test_set_hash_reorder_invariant_after_build():
    r0 = _evidence(sequence=0)
    r1 = _evidence(source="d" * 64, sequence=1)
    h0 = _hypothesis(r0, sequence=0)
    h1 = _hypothesis(r1, proposition="second", sequence=1)
    a = hypothesis.build_hypothesis_set([h0, h1], _ledger([r0, r1]))
    b = hypothesis.build_hypothesis_set([h1, h0], _ledger([r0, r1]))
    assert a.set_hash == b.set_hash


def test_set_hash_changes_with_content():
    r = _evidence()
    a = hypothesis.build_hypothesis_set([_hypothesis(r)], _ledger([r]))
    b = hypothesis.build_hypothesis_set([_hypothesis(r, proposition="other")], _ledger([r]))
    assert a.set_hash != b.set_hash


def test_set_export_detached():
    exported = _valid_set().export()
    exported["hypotheses"][0]["evidence_refs"].append("d" * 64)
    assert len(_valid_set().hypotheses[0].evidence_refs) == 1


def test_set_export_fields():
    assert set(_valid_set().export()) == {"hypotheses", "set_hash"}


def test_verify_valid():
    assert hypothesis.verify_hypothesis_provenance(_valid_set(), _ledger()) is True


def test_verify_wrong_ledger():
    hs = _valid_set()
    other = _evidence(payload="d" * 64)
    with pytest.raises(ValueError):
        hypothesis.verify_hypothesis_provenance(hs, _ledger([other]))


def test_verify_requires_set():
    with pytest.raises(TypeError):
        hypothesis.verify_hypothesis_provenance(object(), _ledger())


def test_verify_requires_ledger():
    with pytest.raises(TypeError):
        hypothesis.verify_hypothesis_provenance(_valid_set(), object())


def test_verify_detects_set_tamper():
    hs = _valid_set()
    forged = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(forged, "hypotheses", hs.hypotheses)
    object.__setattr__(forged, "set_hash", "0" * 64)
    with pytest.raises(ValueError):
        hypothesis.verify_hypothesis_provenance(forged, _ledger())


def test_verify_detects_hypothesis_tamper():
    hs = _valid_set()
    forged_h = object.__new__(hypothesis.Hypothesis)
    object.__setattr__(forged_h, "hypothesis_hash", "0" * 64)
    object.__setattr__(forged_h, "evidence_refs", hs.hypotheses[0].evidence_refs)
    object.__setattr__(forged_h, "state_hash", hs.hypotheses[0].state_hash)
    object.__setattr__(forged_h, "proposition", hs.hypotheses[0].proposition)
    object.__setattr__(forged_h, "sequence", 0)
    forged = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(forged, "hypotheses", (forged_h,))
    object.__setattr__(forged, "set_hash", canonical.replay_hash([forged_h.hypothesis_hash]))
    with pytest.raises(ValueError):
        hypothesis.verify_hypothesis_provenance(forged, _ledger())


def test_provenance_evidence_ref_is_real_hash():
    record = _evidence()
    assert _hypothesis(record).evidence_refs == (record.evidence_hash,)


def test_provenance_state_is_real_state():
    record = _evidence()
    assert _hypothesis(record).state_hash == record.state_hash


def test_hash_formula_is_canonical():
    h = _hypothesis()
    expected = canonical.replay_hash({"evidence_refs": list(h.evidence_refs), "proposition": h.proposition, "sequence": h.sequence, "state_hash": h.state_hash})
    assert h.hypothesis_hash == expected


def test_set_formula_is_canonical():
    hs = _valid_set()
    assert hs.set_hash == canonical.replay_hash([h.hypothesis_hash for h in hs.hypotheses])


def test_multiple_evidence_refs():
    r0 = _evidence(sequence=0)
    r1 = _evidence(source="d" * 64, sequence=1)
    h = hypothesis.Hypothesis((r0.evidence_hash, r1.evidence_hash), STATE, "combined", 0)
    hs = hypothesis.build_hypothesis_set([h], _ledger([r0, r1]))
    assert hs.hypotheses[0].evidence_refs == (r0.evidence_hash, r1.evidence_hash)


def test_multiple_hypotheses():
    r0 = _evidence(sequence=0)
    r1 = _evidence(source="d" * 64, sequence=1)
    h0 = _hypothesis(r0)
    h1 = _hypothesis(r1, proposition="second", sequence=1)
    hs = hypothesis.build_hypothesis_set([h1, h0], _ledger([r0, r1]))
    assert len(hs.hypotheses) == 2


def test_sequence_not_rewritten():
    r0 = _evidence(sequence=0)
    r1 = _evidence(source="d" * 64, sequence=1)
    h0 = _hypothesis(r0)
    h1 = _hypothesis(r1, proposition="second", sequence=1)
    hs = hypothesis.build_hypothesis_set([h1, h0], _ledger([r0, r1]))
    assert hs.hypotheses[0] == h0 and hs.hypotheses[1] == h1


def test_ledger_not_mutated():
    ledger = _ledger()
    before = ledger.export()
    hypothesis.build_hypothesis_set([_hypothesis()], ledger)
    assert ledger.export() == before


def test_hypothesis_input_not_mutated():
    item = _hypothesis()
    before = item.export()
    hypothesis.build_hypothesis_set([item], _ledger())
    assert item.export() == before


def test_repeated_verification_deterministic():
    hs = _valid_set()
    assert hypothesis.verify_hypothesis_provenance(hs, _ledger()) == hypothesis.verify_hypothesis_provenance(hs, _ledger())


def test_same_content_same_identity():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash


def test_detached_hypothesis_roundtrip():
    item = _hypothesis()
    data = item.export()
    rebuilt = hypothesis.Hypothesis(tuple(data["evidence_refs"]), data["state_hash"], data["proposition"], data["sequence"])
    assert rebuilt == item


def test_detached_set_roundtrip():
    hs = _valid_set()
    data = hs.export()
    rebuilt_h = tuple(hypothesis.Hypothesis(tuple(x["evidence_refs"]), x["state_hash"], x["proposition"], x["sequence"]) for x in data["hypotheses"])
    rebuilt = hypothesis.HypothesisSet(rebuilt_h, data["set_hash"])
    assert rebuilt == hs


def test_no_os_import():
    imports = {a.name.split(".")[0] for n in _tree().body if isinstance(n, ast.Import) for a in n.names}
    assert "os" not in imports


def test_no_time_import():
    imports = {a.name.split(".")[0] for n in _tree().body if isinstance(n, ast.Import) for a in n.names}
    assert "time" not in imports


def test_no_random_import():
    imports = {a.name.split(".")[0] for n in _tree().body if isinstance(n, ast.Import) for a in n.names}
    assert "random" not in imports


def test_no_network_imports():
    imports = {a.name.split(".")[0] for n in _tree().body if isinstance(n, ast.Import) for a in n.names}
    assert not imports.intersection({"socket", "requests", "urllib", "httpx"})


def test_no_filesystem_imports():
    imports = {a.name.split(".")[0] for n in _tree().body if isinstance(n, ast.Import) for a in n.names}
    assert not imports.intersection({"pathlib", "shutil", "glob"})


def test_no_identity_call():
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "id" for n in ast.walk(_tree()))


def test_no_builtin_hash_call():
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "hash" for n in ast.walk(_tree()))


def test_no_sorting_calls():
    assert not any(isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id in {"sorted", "sort"}) or (isinstance(n.func, ast.Attribute) and n.func.attr == "sort")) for n in ast.walk(_tree()))

@pytest.mark.parametrize("token", ["score", "confidence", "probability", "bayesian", "fitness", "priority", "threshold", "ranking", "selection", "heuristic", "filtering", "optimization", "objective", "utility", "prediction"])
def test_no_decision_token(token):
    source = inspect.getsource(hypothesis).lower()
    assert token not in source


def test_no_environment_access():
    source = inspect.getsource(hypothesis).lower()
    assert "os.environ" not in source and "getenv" not in source


def test_no_clock_access():
    source = inspect.getsource(hypothesis).lower()
    assert "time.time" not in source and "datetime" not in source


def test_no_uuid_access():
    assert "uuid" not in inspect.getsource(hypothesis).lower()


def test_public_signatures():
    import inspect as _inspect
    assert list(_inspect.signature(hypothesis.build_hypothesis_set).parameters) == ["hypotheses", "ledger"]
    assert list(_inspect.signature(hypothesis.verify_hypothesis_provenance).parameters) == ["hypothesis_set", "ledger"]


def test_verify_returns_bool():
    assert isinstance(hypothesis.verify_hypothesis_provenance(_valid_set(), _ledger()), bool)


def test_empty_set_hash_reproducible():
    a = hypothesis.build_hypothesis_set([], _ledger())
    b = hypothesis.build_hypothesis_set([], _ledger())
    assert a.set_hash == b.set_hash


def test_empty_set_hash_is_canonical():
    hs = hypothesis.build_hypothesis_set([], _ledger())
    assert hs.set_hash == canonical.replay_hash([])


def test_hash_lowercase():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash.lower()


def test_set_hash_lowercase():
    assert _valid_set().set_hash == _valid_set().set_hash.lower()


def test_set_records_are_hypotheses():
    assert all(isinstance(x, hypothesis.Hypothesis) for x in _valid_set().hypotheses)


def test_hypothesis_hash_changes_with_evidence_ref():
    r0 = _evidence()
    r1 = _evidence(source="d" * 64)
    assert _hypothesis(r0).hypothesis_hash != _hypothesis(r1).hypothesis_hash


def test_hypothesis_hash_changes_with_state():
    r0 = _evidence()
    r1 = _evidence(state="d" * 64)
    assert _hypothesis(r0).hypothesis_hash != _hypothesis(r1).hypothesis_hash


def test_provenance_chain_backward_reconstructible():
    record = _evidence()
    hs = hypothesis.build_hypothesis_set([_hypothesis(record)], _ledger([record]))
    assert hs.hypotheses[0].evidence_refs[0] == record.evidence_hash
    assert hs.hypotheses[0].state_hash == record.state_hash


def test_foreign_state_rejected():
    r = _evidence()
    h = hypothesis.Hypothesis((r.evidence_hash,), "d" * 64, P, 0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([h], _ledger([r]))


def test_missing_ref_rejected():
    h = hypothesis.Hypothesis(("e" * 64,), STATE, P, 0)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set([h], _ledger())


def test_empty_evidence_refs_rejected():
    with pytest.raises(ValueError):
        hypothesis.Hypothesis((), STATE, P, 0)


def test_set_member_type_rejected():
    with pytest.raises(TypeError):
        hypothesis.HypothesisSet(("not hypothesis",), canonical.replay_hash(["not hypothesis"]))


def test_set_hash_commitment_binds_members():
    hs = _valid_set()
    other = hypothesis.Hypothesis(("d" * 64,), STATE, P, 0)
    forged = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(forged, "hypotheses", (other,))
    object.__setattr__(forged, "set_hash", hs.set_hash)
    with pytest.raises(ValueError):
        hypothesis.verify_hypothesis_provenance(forged, _ledger())


def test_hypothesis_ref_tuple_cannot_append():
    with pytest.raises(AttributeError):
        _hypothesis().evidence_refs.append("d" * 64)


def test_set_tuple_cannot_append():
    with pytest.raises(AttributeError):
        _valid_set().hypotheses.append(_hypothesis())


def test_state_anchor_frozen():
    with pytest.raises(FrozenInstanceError):
        _hypothesis().state_hash = "d" * 64


def test_sequence_frozen():
    with pytest.raises(FrozenInstanceError):
        _hypothesis().sequence = 1


def test_set_hash_frozen():
    with pytest.raises(FrozenInstanceError):
        _valid_set().set_hash = "d" * 64


def test_no_runtime_environment_names():
    names = {n.id for n in ast.walk(_tree()) if isinstance(n, ast.Name)}
    assert not names.intersection({"environ", "getenv", "random", "time"})


def test_no_network_calls():
    calls = {n.func.id for n in ast.walk(_tree()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls.intersection({"open", "urlopen", "connect"})


def test_content_addressed_identity_uses_replay_hash():
    calls = {n.func.attr for n in ast.walk(_tree()) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "replay_hash" in calls


def test_hypothesis_set_is_immutable_container():
    assert isinstance(_valid_set().hypotheses, tuple)


def test_hypothesis_is_immutable_record():
    assert hypothesis.Hypothesis.__dataclass_params__.frozen is True


def test_set_is_immutable_record():
    assert hypothesis.HypothesisSet.__dataclass_params__.frozen is True


def test_verify_does_not_mutate_set():
    hs = _valid_set()
    before = hs.export()
    hypothesis.verify_hypothesis_provenance(hs, _ledger())
    assert hs.export() == before


def test_build_does_not_mutate_ledger():
    ledger = _ledger()
    before = ledger.export()
    hypothesis.build_hypothesis_set([_hypothesis()], ledger)
    assert ledger.export() == before


def test_build_does_not_mutate_record():
    item = _hypothesis()
    before = item.export()
    hypothesis.build_hypothesis_set([item], _ledger())
    assert item.export() == before


def test_sequence_zero_is_first():
    assert _valid_set().hypotheses[0].sequence == 0


def test_set_contains_input_identity():
    item = _hypothesis()
    hs = hypothesis.build_hypothesis_set([item], _ledger())
    assert hs.hypotheses[0] == item


def test_no_semantic_selection():
    source = inspect.getsource(hypothesis).lower()
    assert all(x not in source for x in ("choose", "prefer", "best", "winner"))


def test_provenance_verification_is_structural():
    assert hypothesis.verify_hypothesis_provenance(_valid_set(), _ledger())


def test_repeated_build_is_stable():
    assert hypothesis.build_hypothesis_set([_hypothesis()], _ledger()) == hypothesis.build_hypothesis_set([_hypothesis()], _ledger())


def test_repeated_export_is_stable():
    assert _valid_set().export() == _valid_set().export()


def test_unicode_proposition_is_stable():
    a = hypothesis.Hypothesis((_evidence().evidence_hash,), STATE, "наблюдение → гипотеза", 0)
    b = hypothesis.Hypothesis((_evidence().evidence_hash,), STATE, "наблюдение → гипотеза", 0)
    assert a.hypothesis_hash == b.hypothesis_hash


def test_canonical_module_is_upstream():
    assert hasattr(canonical, "replay_hash")


def test_evidence_module_is_upstream():
    assert hasattr(evidence, "EvidenceRecord")


def test_no_legacy_hypothesis_import():
    assert "from jamp.research import hypothesis\n" not in inspect.getsource(hypothesis)


def test_public_api_has_no_selection_function():
    assert not any(name.lower() in {"select", "rank", "score", "filter"} for name in dir(hypothesis) if not name.startswith("__"))


def test_proposition_is_not_normalized_semantically():
    a = hypothesis.Hypothesis((_evidence().evidence_hash,), STATE, "P", 0)
    b = hypothesis.Hypothesis((_evidence().evidence_hash,), STATE, " P ", 0)
    assert a.hypothesis_hash != b.hypothesis_hash


def test_sequence_participates_in_identity():
    r0 = _evidence(sequence=0)
    r1 = _evidence(sequence=1)
    assert _hypothesis(r0, sequence=0).hypothesis_hash != _hypothesis(r1, sequence=1).hypothesis_hash


def test_state_anchor_participates_in_identity():
    r0 = _evidence(state=STATE)
    r1 = _evidence(state="d" * 64)
    assert _hypothesis(r0).state_hash != _hypothesis(r1).state_hash


def test_set_identity_is_content_addressed():
    hs = _valid_set()
    assert hs.set_hash == canonical.replay_hash([hs.hypotheses[0].hypothesis_hash])


def test_final_provenance_truth():
    assert hypothesis.verify_hypothesis_provenance(_valid_set(), _ledger()) is True
