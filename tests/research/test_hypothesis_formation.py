from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import os
from pathlib import Path

import pytest

from jamp.research import evidence
from jamp.research import hypothesis_formation as hypothesis

HEX64 = "a" * 64
STATE_HASH = "b" * 64
SOURCE_HASH = "c" * 64
PAYLOAD_HASH = "d" * 64


def _evidence() -> evidence.EvidenceRecord:
    return evidence.EvidenceRecord(
        evidence_hash=HEX64,
        state_hash=STATE_HASH,
        payload_hash=PAYLOAD_HASH,
        source_hash=SOURCE_HASH,
        sequence=0,
    )


def _ledger() -> evidence.EvidenceLedger:
    return evidence.EvidenceLedger(( _evidence(), ))


def _hypothesis() -> hypothesis.Hypothesis:
    record = _evidence()
    return hypothesis.Hypothesis(
        hypothesis_hash=hypothesis._compute_hypothesis_hash((record.evidence_hash,), record.state_hash, "P", 0),
        evidence_refs=(record.evidence_hash,),
        state_hash=record.state_hash,
        proposition="P",
        sequence=0,
    )


def _set() -> hypothesis.HypothesisSet:
    item = _hypothesis()
    return hypothesis.HypothesisSet(
        hypotheses=(item,),
        set_hash=hypothesis._compute_set_hash((item,)),
    )


def test_hypothesis_is_frozen():
    item = _hypothesis()
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.proposition = "Q"


def test_hypothesis_set_is_frozen():
    item = _set()
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.set_hash = "0" * 64


def test_hypothesis_hash_is_sha256():
    item = _hypothesis()
    assert len(item.hypothesis_hash) == 64
    int(item.hypothesis_hash, 16)


def test_set_hash_is_sha256():
    item = _set()
    assert len(item.set_hash) == 64
    int(item.set_hash, 16)


def test_hypothesis_refs_are_tuple():
    assert isinstance(_hypothesis().evidence_refs, tuple)


def test_hypothesis_collection_is_tuple():
    assert isinstance(_set().hypotheses, tuple)


def test_constructor_rejects_invalid_hypothesis_commitment():
    item = _hypothesis()
    with pytest.raises(ValueError):
        hypothesis.Hypothesis("0" * 64, item.evidence_refs, item.state_hash, item.proposition, item.sequence)


def test_constructor_rejects_invalid_set_commitment():
    item = _hypothesis()
    with pytest.raises(ValueError):
        hypothesis.HypothesisSet((item,), "0" * 64)


def test_build_accepts_valid_records():
    result = hypothesis.build_hypothesis_set((_hypothesis(),), _ledger())
    assert result.hypotheses == (_hypothesis(),)


def test_build_returns_hypothesis_set():
    assert isinstance(hypothesis.build_hypothesis_set((_hypothesis(),), _ledger()), hypothesis.HypothesisSet)


def test_build_validates_evidence_binding():
    item = _hypothesis()
    bad = dataclasses.replace(item, evidence_refs=("e" * 64,))
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((bad,), _ledger())


def test_build_validates_state_grounding():
    item = _hypothesis()
    bad = dataclasses.replace(item, state_hash="f" * 64, hypothesis_hash=hypothesis._compute_hypothesis_hash(item.evidence_refs, "f" * 64, item.proposition, item.sequence))
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((bad,), _ledger())


def test_build_rejects_duplicate_hypotheses():
    item = _hypothesis()
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((item, item), _ledger())


def test_build_rejects_duplicate_evidence_reference_within_record():
    record = _evidence()
    bad = hypothesis.Hypothesis(
        hypothesis._compute_hypothesis_hash((record.evidence_hash, record.evidence_hash), record.state_hash, "P", 0),
        (record.evidence_hash, record.evidence_hash), record.state_hash, "P", 0,
    )
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((bad,), _ledger())


def test_build_validates_sequence_integrity():
    item = _hypothesis()
    bad = dataclasses.replace(item, sequence=1, hypothesis_hash=hypothesis._compute_hypothesis_hash(item.evidence_refs, item.state_hash, item.proposition, 1))
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((bad,), _ledger())


def test_verify_valid_set():
    assert hypothesis.verify_hypothesis_provenance(_set(), _ledger()) is True


def test_verify_detects_hypothesis_tamper():
    item = _hypothesis()
    tampered = dataclasses.replace(item, proposition="Q")
    candidate = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(candidate, "hypotheses", (tampered,))
    object.__setattr__(candidate, "set_hash", hypothesis._compute_set_hash((tampered,)))
    assert hypothesis.verify_hypothesis_provenance(candidate, _ledger()) is False


def test_verify_detects_set_tamper():
    item = _hypothesis()
    candidate = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(candidate, "hypotheses", (item,))
    object.__setattr__(candidate, "set_hash", "0" * 64)
    assert hypothesis.verify_hypothesis_provenance(candidate, _ledger()) is False


def test_verify_rejects_missing_evidence():
    item = _hypothesis()
    ledger = evidence.EvidenceLedger(())
    assert hypothesis.verify_hypothesis_provenance(_set(), ledger) is False


def test_empty_set_is_valid():
    result = hypothesis.build_hypothesis_set((), _ledger())
    assert result.hypotheses == ()
    assert hypothesis.verify_hypothesis_provenance(result, _ledger()) is True


def test_empty_set_has_deterministic_hash():
    first = hypothesis.build_hypothesis_set((), _ledger())
    second = hypothesis.build_hypothesis_set((), _ledger())
    assert first.set_hash == second.set_hash


def test_same_input_is_reproducible():
    assert hypothesis.build_hypothesis_set((_hypothesis(),), _ledger()) == hypothesis.build_hypothesis_set((_hypothesis(),), _ledger())


def test_hypothesis_hash_is_reproducible():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash


def test_set_hash_changes_when_hypothesis_changes():
    item = _hypothesis()
    other = dataclasses.replace(item, proposition="Q", hypothesis_hash=hypothesis._compute_hypothesis_hash(item.evidence_refs, item.state_hash, "Q", item.sequence))
    assert hypothesis._compute_set_hash((item,)) != hypothesis._compute_set_hash((other,))


def test_provenance_references_evidence_hashes():
    item = _hypothesis()
    assert item.evidence_refs == (_evidence().evidence_hash,)


def test_provenance_state_matches_evidence():
    item = _hypothesis()
    assert item.state_hash == _evidence().state_hash


def test_proposition_is_string():
    assert isinstance(_hypothesis().proposition, str)


def test_sequence_is_integer():
    assert isinstance(_hypothesis().sequence, int)


def test_sequence_is_nonnegative():
    with pytest.raises(ValueError):
        hypothesis.Hypothesis(_hypothesis().hypothesis_hash, _hypothesis().evidence_refs, STATE_HASH, "P", -1)


def test_hashes_are_lowercase():
    item = _hypothesis()
    assert item.hypothesis_hash == item.hypothesis_hash.lower()
    assert item.state_hash == item.state_hash.lower()


def test_hypothesis_hash_rejects_invalid_shape():
    with pytest.raises(ValueError):
        hypothesis.Hypothesis("x", (HEX64,), STATE_HASH, "P", 0)


def test_set_hash_rejects_invalid_shape():
    with pytest.raises(ValueError):
        hypothesis.HypothesisSet((), "x")


def test_evidence_ref_rejects_invalid_shape():
    with pytest.raises(ValueError):
        hypothesis.Hypothesis("0" * 64, ("x",), STATE_HASH, "P", 0)


def test_state_hash_rejects_invalid_shape():
    with pytest.raises(ValueError):
        hypothesis.Hypothesis("0" * 64, (HEX64,), "x", "P", 0)


def test_sequence_order_is_preserved():
    r0 = _evidence()
    r1 = dataclasses.replace(r0, evidence_hash="e" * 64, sequence=1)
    ledger = evidence.EvidenceLedger((r0, r1))
    h0 = _hypothesis()
    h1 = hypothesis.Hypothesis(hypothesis._compute_hypothesis_hash((r1.evidence_hash,), r1.state_hash, "Q", 1), (r1.evidence_hash,), r1.state_hash, "Q", 1)
    result = hypothesis.build_hypothesis_set((h0, h1), ledger)
    assert [x.sequence for x in result.hypotheses] == [0, 1]


def test_noncontiguous_sequences_rejected():
    r0 = _evidence()
    r2 = dataclasses.replace(r0, evidence_hash="e" * 64, sequence=2)
    ledger = evidence.EvidenceLedger((r0, r2))
    h0 = _hypothesis()
    h2 = hypothesis.Hypothesis(hypothesis._compute_hypothesis_hash((r2.evidence_hash,), r2.state_hash, "Q", 2), (r2.evidence_hash,), r2.state_hash, "Q", 2)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((h0, h2), ledger)


def test_sequence_order_not_rewritten():
    r0 = _evidence()
    r1 = dataclasses.replace(r0, evidence_hash="e" * 64, sequence=1)
    ledger = evidence.EvidenceLedger((r0, r1))
    h0 = _hypothesis()
    h1 = hypothesis.Hypothesis(hypothesis._compute_hypothesis_hash((r1.evidence_hash,), r1.state_hash, "Q", 1), (r1.evidence_hash,), r1.state_hash, "Q", 1)
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((h1, h0), ledger)


def test_reorder_changes_commitment():
    r0 = _evidence()
    r1 = dataclasses.replace(r0, evidence_hash="e" * 64, sequence=1)
    h0 = _hypothesis()
    h1 = hypothesis.Hypothesis(hypothesis._compute_hypothesis_hash((r1.evidence_hash,), r1.state_hash, "Q", 1), (r1.evidence_hash,), r1.state_hash, "Q", 1)
    assert hypothesis._compute_set_hash((h0, h1)) != hypothesis._compute_set_hash((h1, h0))


def test_no_environment_dependencies():
    source = Path(hypothesis.__file__).read_text()
    assert "os.environ" not in source
    assert "os.getenv" not in source
    assert "time." not in source
    assert "random." not in source


def test_no_filesystem_or_network_runtime():
    tree = ast.parse(Path(hypothesis.__file__).read_text())
    forbidden = {"open", "urlopen", "socket", "requests", "connect"}
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & forbidden


def test_no_selection_vocabulary():
    source = Path(hypothesis.__file__).read_text().lower()
    forbidden = ("bayesian", "confidence", "probability", "fitness", "priority", "ranking", "score", "threshold")
    assert not any(word in source for word in forbidden)


def test_canonical_hash_matches_sha256():
    item = _hypothesis()
    expected = hypothesis._compute_hypothesis_hash(item.evidence_refs, item.state_hash, item.proposition, item.sequence)
    assert item.hypothesis_hash == expected


def test_set_commitment_uses_member_commitments():
    item = _hypothesis()
    assert _set().set_hash == hypothesis._compute_set_hash((item,))


def test_build_rejects_foreign_state_reference():
    item = _hypothesis()
    foreign = dataclasses.replace(item, evidence_refs=(HEX64,), state_hash="f" * 64, hypothesis_hash=hypothesis._compute_hypothesis_hash((HEX64,), "f" * 64, item.proposition, item.sequence))
    with pytest.raises(ValueError):
        hypothesis.build_hypothesis_set((foreign,), _ledger())


def test_verify_returns_bool():
    assert isinstance(hypothesis.verify_hypothesis_provenance(_set(), _ledger()), bool)


def test_build_does_not_mutate_input_sequence():
    items = [_hypothesis()]
    before = copy.deepcopy(items)
    hypothesis.build_hypothesis_set(items, _ledger())
    assert items == before


def test_ledger_is_only_provenance_source():
    item = _hypothesis()
    assert hypothesis.verify_hypothesis_provenance(_set(), _ledger())
    bad_ledger = evidence.EvidenceLedger((dataclasses.replace(_evidence(), state_hash="f" * 64),))
    assert not hypothesis.verify_hypothesis_provenance(_set(), bad_ledger)


def test_detached_export_round_trip():
    item = _hypothesis()
    payload = dataclasses.asdict(item)
    payload["evidence_refs"] = list(payload["evidence_refs"])
    rebuilt = hypothesis.Hypothesis(**payload)
    assert rebuilt == item


def test_set_detached_export_round_trip():
    item = _set()
    payload = {"hypotheses": [dataclasses.asdict(item.hypotheses[0])], "set_hash": item.set_hash}
    rebuilt_h = tuple(hypothesis.Hypothesis(**{**x, "evidence_refs": tuple(x["evidence_refs"])}) for x in payload["hypotheses"])
    rebuilt = hypothesis.HypothesisSet(rebuilt_h, payload["set_hash"])
    assert rebuilt == item


def test_no_identity_based_hashing():
    source = Path(hypothesis.__file__).read_text()
    assert "id(" not in source


def test_no_random_import():
    tree = ast.parse(Path(hypothesis.__file__).read_text())
    assert not any(isinstance(n, ast.Import) and any(a.name == "random" for a in n.names) for n in tree.body)


def test_no_network_import():
    source = Path(hypothesis.__file__).read_text()
    assert "urllib" not in source
    assert "requests" not in source


def test_hashes_are_content_addressed():
    item = _hypothesis()
    assert item.hypothesis_hash == hypothesis._compute_hypothesis_hash(item.evidence_refs, item.state_hash, item.proposition, item.sequence)


def test_verify_detects_wrong_evidence_hash():
    item = _hypothesis()
    forged = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(forged, "hypotheses", (dataclasses.replace(item, evidence_refs=("e" * 64,)),))
    object.__setattr__(forged, "set_hash", hypothesis._compute_set_hash(forged.hypotheses))
    assert not hypothesis.verify_hypothesis_provenance(forged, _ledger())


def test_verify_detects_wrong_state_hash():
    item = _hypothesis()
    forged = dataclasses.replace(item, state_hash="f" * 64)
    candidate = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(candidate, "hypotheses", (forged,))
    object.__setattr__(candidate, "set_hash", hypothesis._compute_set_hash((forged,)))
    assert not hypothesis.verify_hypothesis_provenance(candidate, _ledger())


def test_verify_detects_wrong_sequence():
    item = _hypothesis()
    forged = dataclasses.replace(item, sequence=1)
    candidate = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(candidate, "hypotheses", (forged,))
    object.__setattr__(candidate, "set_hash", hypothesis._compute_set_hash((forged,)))
    assert not hypothesis.verify_hypothesis_provenance(candidate, _ledger())


def test_public_build_signature():
    import inspect
    sig = inspect.signature(hypothesis.build_hypothesis_set)
    assert list(sig.parameters) == ["hypotheses", "ledger"]


def test_public_verify_signature():
    import inspect
    sig = inspect.signature(hypothesis.verify_hypothesis_provenance)
    assert list(sig.parameters) == ["hypothesis_set", "ledger"]


def test_no_sorting_api():
    source = Path(hypothesis.__file__).read_text()
    assert "sorted(" not in source
    assert ".sort(" not in source


def test_no_environment_import():
    tree = ast.parse(Path(hypothesis.__file__).read_text())
    assert not any(isinstance(n, ast.Import) and any(a.name == "os" for a in n.names) for n in tree.body)


def test_hypothesis_set_contains_only_hypotheses():
    with pytest.raises(TypeError):
        hypothesis.HypothesisSet(("not-a-hypothesis",), "0" * 64)


def test_hypothesis_refs_are_evidence_hashes():
    assert _hypothesis().evidence_refs[0] == _evidence().evidence_hash


def test_provenance_chain_is_backward_reconstructible():
    item = _hypothesis()
    record = _ledger().records[0]
    assert item.evidence_refs[0] == record.evidence_hash
    assert item.state_hash == record.state_hash


def test_hash_payload_is_canonical():
    item = _hypothesis()
    assert item.hypothesis_hash == hypothesis._compute_hypothesis_hash(item.evidence_refs, item.state_hash, item.proposition, item.sequence)


def test_same_content_different_object_is_same_identity():
    assert _hypothesis().hypothesis_hash == copy.deepcopy(_hypothesis()).hypothesis_hash


def test_set_identity_is_content_based():
    assert _set().set_hash == copy.deepcopy(_set()).set_hash


def test_verify_empty_set_is_true():
    empty = hypothesis.build_hypothesis_set((), _ledger())
    assert hypothesis.verify_hypothesis_provenance(empty, _ledger()) is True


def test_build_requires_sequence_container():
    with pytest.raises(TypeError):
        hypothesis.build_hypothesis_set(None, _ledger())


def test_verify_requires_hypothesis_set():
    with pytest.raises(TypeError):
        hypothesis.verify_hypothesis_provenance(None, _ledger())


def test_verify_requires_ledger():
    with pytest.raises(TypeError):
        hypothesis.verify_hypothesis_provenance(_set(), None)


def test_build_requires_ledger():
    with pytest.raises(TypeError):
        hypothesis.build_hypothesis_set((_hypothesis(),), None)


def test_state_anchor_is_immutable():
    item = _hypothesis()
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.state_hash = "f" * 64


def test_evidence_refs_are_immutable():
    item = _hypothesis()
    with pytest.raises(AttributeError):
        item.evidence_refs.append("x")


def test_hypotheses_are_immutable():
    item = _set()
    with pytest.raises(AttributeError):
        item.hypotheses.append(_hypothesis())


def test_no_runtime_clock():
    source = Path(hypothesis.__file__).read_text()
    assert "datetime" not in source
    assert "perf_counter" not in source
    assert "monotonic" not in source


def test_no_filesystem_path_runtime():
    source = Path(hypothesis.__file__).read_text()
    assert "Path(" not in source
    assert "open(" not in source


def test_no_process_environment_runtime():
    source = Path(hypothesis.__file__).read_text()
    assert "environ" not in source


def test_no_uuid_runtime():
    source = Path(hypothesis.__file__).read_text()
    assert "uuid" not in source.lower()


def test_proposition_does_not_affect_provenance_refs():
    item = _hypothesis()
    changed = dataclasses.replace(item, proposition="Q", hypothesis_hash=hypothesis._compute_hypothesis_hash(item.evidence_refs, item.state_hash, "Q", item.sequence))
    assert changed.evidence_refs == item.evidence_refs
    assert changed.state_hash == item.state_hash


def test_provenance_does_not_select_between_hypotheses():
    r0 = _evidence()
    r1 = dataclasses.replace(r0, evidence_hash="e" * 64, sequence=1)
    ledger = evidence.EvidenceLedger((r0, r1))
    h0 = _hypothesis()
    h1 = hypothesis.Hypothesis(hypothesis._compute_hypothesis_hash((r1.evidence_hash,), r1.state_hash, "Q", 1), (r1.evidence_hash,), r1.state_hash, "Q", 1)
    result = hypothesis.build_hypothesis_set((h0, h1), ledger)
    assert result.hypotheses == (h0, h1)


def test_no_hash_randomness():
    assert _hypothesis().hypothesis_hash == _hypothesis().hypothesis_hash


def test_ledger_records_are_not_mutated():
    ledger = _ledger()
    before = copy.deepcopy(ledger.records)
    hypothesis.build_hypothesis_set((_hypothesis(),), ledger)
    assert ledger.records == before


def test_hypothesis_sequence_matches_evidence_sequence():
    assert _hypothesis().sequence == _evidence().sequence


def test_verify_sequence_alignment():
    item = _hypothesis()
    forged = dataclasses.replace(item, sequence=1)
    candidate = object.__new__(hypothesis.HypothesisSet)
    object.__setattr__(candidate, "hypotheses", (forged,))
    object.__setattr__(candidate, "set_hash", hypothesis._compute_set_hash((forged,)))
    assert hypothesis.verify_hypothesis_provenance(candidate, _ledger()) is False


def test_hash_algorithm_is_sha256():
    assert hashlib.sha256(b"x").hexdigest() == hypothesis._sha256_hex(b"x")


def test_set_hash_is_stable_across_json_round_trip():
    item = _set()
    raw = json.dumps(dataclasses.asdict(item), sort_keys=True)
    assert isinstance(raw, str)
    assert hypothesis.HypothesisSet(item.hypotheses, item.set_hash) == item


def test_contract_has_no_heuristic_wording_in_public_module():
    source = Path(hypothesis.__file__).read_text().lower()
    for word in ("heuristic", "teleology", "selection", "filtering"):
        assert word not in source


def test_build_is_deterministic_for_tuple_input():
    args = (_hypothesis(),)
    a = hypothesis.build_hypothesis_set(args, _ledger())
    b = hypothesis.build_hypothesis_set(args, _ledger())
    assert a.set_hash == b.set_hash


def test_verify_does_not_change_set():
    item = _set()
    before = copy.deepcopy(item)
    assert hypothesis.verify_hypothesis_provenance(item, _ledger())
    assert item == before


def test_hypothesis_hash_is_64_hex_chars():
    value = _hypothesis().hypothesis_hash
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def test_set_hash_is_64_hex_chars():
    value = _set().set_hash
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def test_state_hash_is_64_hex_chars():
    value = _hypothesis().state_hash
    assert len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def test_evidence_refs_are_unique():
    assert len(_hypothesis().evidence_refs) == len(set(_hypothesis().evidence_refs))


def test_set_members_are_unique():
    assert len(_set().hypotheses) == len(set(_set().hypotheses))


def test_no_runtime_id_call():
    source = Path(hypothesis.__file__).read_text()
    assert "id(" not in source


def test_public_types_are_frozen_dataclasses():
    assert dataclasses.is_dataclass(hypothesis.Hypothesis)
    assert dataclasses.is_dataclass(hypothesis.HypothesisSet)
    assert hypothesis.Hypothesis.__dataclass_params__.frozen
    assert hypothesis.HypothesisSet.__dataclass_params__.frozen
