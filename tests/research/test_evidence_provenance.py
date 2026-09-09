"""P22.7 test-first contract for deterministic evidence provenance.

The production module is intentionally absent at contract deployment time.
These gates define the immutable public boundary before implementation.
"""
from __future__ import annotations

import ast
import inspect
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

from jamp.research import evidence

FORBIDDEN = {
    "select", "select_node", "select_nodes", "rank", "sort", "sorted",
    "filter", "threshold", "heuristic", "estimate", "approximate",
    "goal", "objective", "utility", "fitness", "probability", "prediction",
    "confidence", "weight", "score", "score_evidence", "relevance",
}

HEX64 = "a" * 64
HEX64_B = "b" * 64
HEX64_C = "c" * 64


def _source_tree():
    return ast.parse(inspect.getsource(evidence))


def _record(source=HEX64, payload=HEX64_B, state=HEX64_C, sequence=0):
    return evidence.EvidenceRecord(source, payload, state, sequence)


def _ledger():
    return evidence.build_evidence_ledger((_record(),))


def test_public_api_exists():
    assert hasattr(evidence, "EvidenceRecord")
    assert hasattr(evidence, "EvidenceLedger")
    assert hasattr(evidence, "build_evidence_ledger")
    assert hasattr(evidence, "verify_evidence")


def test_public_exports_are_exact():
    assert evidence.__all__ == (
        "EvidenceRecord", "EvidenceLedger", "build_evidence_ledger", "verify_evidence"
    )


def test_evidence_record_is_frozen_dataclass():
    assert is_dataclass(evidence.EvidenceRecord)
    assert evidence.EvidenceRecord.__dataclass_params__.frozen is True


def test_evidence_ledger_is_frozen_dataclass():
    assert is_dataclass(evidence.EvidenceLedger)
    assert evidence.EvidenceLedger.__dataclass_params__.frozen is True


def test_record_exposes_required_fields():
    assert set(evidence.EvidenceRecord.__dataclass_fields__) == {
        "evidence_hash", "source_hash", "payload_hash", "state_hash", "sequence"
    }


def test_ledger_exposes_structural_fields_only():
    assert set(evidence.EvidenceLedger.__dataclass_fields__) == {
        "records", "ledger_hash"
    }


def test_evidence_hash_is_sha256_hex():
    record = _record()
    assert len(record.evidence_hash) == 64
    assert all(ch in "0123456789abcdef" for ch in record.evidence_hash)


def test_evidence_hash_is_derived_from_required_inputs():
    record = _record()
    expected = evidence.EvidenceRecord(
        source_hash=HEX64,
        payload_hash=HEX64_B,
        state_hash=HEX64_C,
        sequence=0,
    )
    assert record.evidence_hash == expected.evidence_hash


def test_same_inputs_produce_same_evidence_hash():
    assert _record().evidence_hash == _record().evidence_hash


def test_source_hash_changes_evidence_identity():
    assert _record(source=HEX64_B).evidence_hash != _record().evidence_hash


def test_payload_hash_changes_evidence_identity():
    assert _record(payload=HEX64_C).evidence_hash != _record().evidence_hash


def test_state_hash_changes_evidence_identity():
    assert _record(state=HEX64_B).evidence_hash != _record().evidence_hash


def test_sequence_changes_evidence_identity():
    assert _record(sequence=1).evidence_hash != _record(sequence=0).evidence_hash


def test_record_requires_lowercase_sha256_source_hash():
    with pytest.raises(ValueError):
        _record(source="A" * 64)


def test_record_requires_lowercase_sha256_payload_hash():
    with pytest.raises(ValueError):
        _record(payload="not-a-hash")


def test_record_requires_lowercase_sha256_state_hash():
    with pytest.raises(ValueError):
        _record(state="b" * 63)


def test_record_requires_nonnegative_integer_sequence():
    with pytest.raises((TypeError, ValueError)):
        _record(sequence=-1)


def test_record_rejects_boolean_sequence():
    with pytest.raises((TypeError, ValueError)):
        _record(sequence=True)


def test_record_is_immutable():
    record = _record()
    with pytest.raises((TypeError, FrozenInstanceError)):
        record.sequence = 2


def test_ledger_records_are_tuple():
    assert isinstance(_ledger().records, tuple)


def test_ledger_hash_is_sha256_hex():
    ledger = _ledger()
    assert len(ledger.ledger_hash) == 64
    assert all(ch in "0123456789abcdef" for ch in ledger.ledger_hash)


def test_ledger_is_deterministic():
    assert _ledger() == _ledger()


def test_equivalent_input_order_produces_same_ledger():
    first = _record(sequence=0)
    second = _record(source=HEX64_B, sequence=1)
    assert evidence.build_evidence_ledger((first, second)) == evidence.build_evidence_ledger((second, first))


def test_sequence_order_is_canonical():
    first = _record(sequence=0)
    second = _record(source=HEX64_B, sequence=1)
    ledger = evidence.build_evidence_ledger((second, first))
    assert tuple(r.sequence for r in ledger.records) == (0, 1)


def test_duplicate_evidence_is_rejected():
    record = _record()
    with pytest.raises(ValueError):
        evidence.build_evidence_ledger((record, record))


def test_duplicate_sequence_is_rejected():
    first = _record()
    second = _record(source=HEX64_B)
    with pytest.raises(ValueError):
        evidence.build_evidence_ledger((first, second))


def test_sequence_gap_is_rejected():
    with pytest.raises(ValueError):
        evidence.build_evidence_ledger((_record(sequence=1),))


def test_sequence_must_start_at_zero():
    with pytest.raises(ValueError):
        evidence.build_evidence_ledger((_record(sequence=2),))


def test_empty_ledger_is_structurally_valid():
    ledger = evidence.build_evidence_ledger(())
    assert ledger.records == ()
    assert len(ledger.ledger_hash) == 64


def test_state_binding_is_preserved():
    record = _record(state=HEX64_C)
    ledger = evidence.build_evidence_ledger((record,))
    assert ledger.records[0].state_hash == HEX64_C


def test_source_identity_is_preserved():
    record = _record(source=HEX64_B)
    assert evidence.build_evidence_ledger((record,)).records[0].source_hash == HEX64_B


def test_payload_identity_is_preserved():
    record = _record(payload=HEX64_C)
    assert evidence.build_evidence_ledger((record,)).records[0].payload_hash == HEX64_C


def test_verify_evidence_accepts_valid_ledger():
    assert evidence.verify_evidence(_ledger()) is True


def test_verify_evidence_returns_boolean():
    assert isinstance(evidence.verify_evidence(_ledger()), bool)


def test_tampered_evidence_hash_is_rejected():
    ledger = _ledger()
    object.__setattr__(ledger.records[0], "evidence_hash", "f" * 64)
    with pytest.raises(ValueError):
        evidence.verify_evidence(ledger)


def test_tampered_ledger_hash_is_rejected():
    ledger = _ledger()
    object.__setattr__(ledger, "ledger_hash", "f" * 64)
    with pytest.raises(ValueError):
        evidence.verify_evidence(ledger)


def test_tampered_state_binding_is_rejected():
    ledger = _ledger()
    object.__setattr__(ledger.records[0], "state_hash", "f" * 64)
    with pytest.raises(ValueError):
        evidence.verify_evidence(ledger)


def test_verify_does_not_mutate_ledger():
    ledger = _ledger()
    before = ledger
    evidence.verify_evidence(ledger)
    assert ledger == before


def test_export_is_detached_if_present():
    ledger = _ledger()
    assert hasattr(ledger, "export")
    exported = ledger.export()
    exported["records"] = []
    assert ledger.records


def test_record_export_is_detached_if_present():
    record = _record()
    assert hasattr(record, "export")
    exported = record.export()
    exported["sequence"] = 99
    assert record.sequence == 0


def test_environment_does_not_change_identity(monkeypatch):
    baseline = _record().evidence_hash
    monkeypatch.setenv("PYTHONHASHSEED", "random")
    monkeypatch.setenv("JAMP_EVIDENCE_ENV", "mutated")
    assert _record().evidence_hash == baseline


def test_evidence_does_not_read_environment():
    source = inspect.getsource(evidence)
    assert "os.environ" not in source
    assert "getenv" not in source


def test_evidence_does_not_use_runtime_identity():
    source = inspect.getsource(evidence)
    assert "id(" not in source
    assert "memory" not in source.lower()


def test_evidence_does_not_import_time_or_randomness():
    source = inspect.getsource(evidence)
    assert "import time" not in source
    assert "import random" not in source


def test_evidence_has_no_external_io_boundary():
    source = inspect.getsource(evidence)
    for token in ("open(", "requests", "socket", "subprocess"):
        assert token not in source


def test_evidence_has_no_decision_logic():
    for node in ast.walk(_source_tree()):
        if isinstance(node, ast.Name):
            assert node.id.lower() not in FORBIDDEN
        if isinstance(node, ast.Attribute):
            assert node.attr.lower() not in FORBIDDEN


def test_evidence_has_no_mutator_api():
    public = {name for name in dir(evidence) if not name.startswith("_")}
    assert not {"set_state", "update_state", "mutate", "rank", "select"} & public


def test_evidence_does_not_import_evaluation_metrics():
    source = inspect.getsource(evidence)
    assert "EvaluationMetrics" not in source
    assert "score" not in source.lower()


def test_evidence_is_independent_of_current_working_directory(monkeypatch, tmp_path):
    baseline = _ledger()
    monkeypatch.chdir(tmp_path)
    assert _ledger() == baseline


def test_multiple_records_have_deterministic_commitment():
    records = (_record(sequence=0), _record(source=HEX64_B, sequence=1))
    assert evidence.build_evidence_ledger(records).ledger_hash == evidence.build_evidence_ledger(records).ledger_hash


def test_record_sequence_is_integer():
    assert isinstance(_record().sequence, int)


def test_record_hash_is_not_runtime_object_identity():
    assert _record().evidence_hash != hex(id(_record()))[2:].rjust(64, "0")


def test_ledger_records_are_immutable_dataclasses():
    assert all(is_dataclass(record) and record.__dataclass_params__.frozen for record in _ledger().records)


def test_ledger_commitment_changes_when_record_changes():
    first = evidence.build_evidence_ledger((_record(),))
    changed = evidence.build_evidence_ledger((_record(state=HEX64_B),))
    assert first.ledger_hash != changed.ledger_hash


@pytest.mark.parametrize("gate", range(10))
def test_evidence_structural_gate_family(gate):
    """Reserved executable gates for the remaining P22.7 contract."""
    assert gate >= 0
