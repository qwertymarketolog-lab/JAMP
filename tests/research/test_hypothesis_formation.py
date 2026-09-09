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
    assert "pathlib" not in imports


def test_no_environment_access():
    source = inspect.getsource(hypothesis)
    assert "environ" not in source
    assert "getenv" not in source


def test_no_runtime_time_access():
    source = inspect.getsource(hypothesis)
    assert "time." not in source
    assert "datetime" not in source


def test_no_network_calls():
    source = inspect.getsource(hypothesis)
    assert "requests." not in source
    assert "urllib." not in source
    assert "httpx." not in source
    assert "socket." not in source


def test_no_decision_token():
    source = inspect.getsource(hypothesis).lower()
    for token in ("score", "confidence", "probability", "ranking", "priority", "fitness", "threshold", "bayesian"):
        assert token not in source


def test_no_semantic_selection():
    source = inspect.getsource(hypothesis).lower()
    for token in ("choose", "prefer", "best", "winner"):
        assert token not in source


def test_no_selection_functions():
    names = {node.name for node in _tree().body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not any(any(token in name.lower() for token in ("select", "rank", "score", "filter", "choose")) for name in names)


def test_no_io_calls():
    names = {
        node.func.attr
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not names.intersection({"open", "connect", "urlopen", "request", "getenv"})


def test_no_legacy_hypothesis_import():
    source = inspect.getsource(hypothesis)
    assert "from .hypothesis import" not in source


def test_public_api_has_no_selection_primitive():
    assert not any(name.lower().startswith(("select", "rank", "score", "filter")) for name in hypothesis.__all__)


def test_set_commitment_changes_on_hypothesis_change():
    r = _evidence()
    a = hypothesis.build_hypothesis_set([_hypothesis(r)], _ledger([r]))
    b = hypothesis.build_hypothesis_set([_hypothesis(r, proposition="changed")], _ledger([r]))
    assert a.set_hash != b.set_hash


def test_verify_rejects_forged_state():
    hs = _valid_set()
    original = hs.hypotheses[0]
    forged_h = object.__new__(hypothesis.Hypothesis)
    object.__setattr__(forged_h, "hypothesis_hash", original.hypothesis_hash)
    object.__setattr__(forged_h, "evidence_refs", original.evidence_refs)
    object.__setattr__(forged_h, "state_hash", "d" * 64)
    object.__setattr__(forged_h, "proposition", original.proposition)
    object.__setattr__(forged_h, "sequence", original.sequence)
    forged = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(forged, "hypotheses", (forged_h,))
    object.__setattr__(forged, "set_hash", canonical.replay_hash([forged_h.hypothesis_hash]))
    with pytest.raises(ValueError):
        hypothesis.verify_hypothesis_provenance(forged, _ledger())


def test_verify_repeatedly_is_stable():
    hs = _valid_set()
    for _ in range(5):
        assert hypothesis.verify_hypothesis_provenance(hs, _ledger()) is True


def test_build_does_not_mutate_sequence_input():
    records = [_evidence()]
    items = [_hypothesis(records[0])]
    snapshot = list(items)
    hypothesis.build_hypothesis_set(items, _ledger(records))
    assert items == snapshot


def test_export_roundtrip_hash_stable():
    item = _hypothesis()
    data = item.export()
    rebuilt = hypothesis.Hypothesis(tuple(data["evidence_refs"]), data["state_hash"], data["proposition"], data["sequence"])
    assert rebuilt.hypothesis_hash == item.hypothesis_hash


def test_set_export_roundtrip_hash_stable():
    hs = _valid_set()
    data = hs.export()
    rebuilt_h = tuple(hypothesis.Hypothesis(tuple(x["evidence_refs"]), x["state_hash"], x["proposition"], x["sequence"]) for x in data["hypotheses"])
    rebuilt = hypothesis.HypothesisSet(rebuilt_h, data["set_hash"])
    assert rebuilt.set_hash == hs.set_hash


def test_environment_independence_shape():
    assert isinstance(_valid_set().set_hash, str)


def test_no_stdout_stderr_calls():
    names = {
        node.func.attr
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not names.intersection({"print", "write", "flush"})


def test_provenance_truth_is_boolean():
    assert hypothesis.verify_hypothesis_provenance(_valid_set(), _ledger()) is True


def test_duplicate_evidence_refs_rejected():
    record = _evidence()
    with pytest.raises(ValueError):
        hypothesis.Hypothesis(
            (record.evidence_hash, record.evidence_hash),
            record.state_hash,
            P,
            0,
        )
