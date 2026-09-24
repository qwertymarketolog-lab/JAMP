from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from jamp_1c.identity import compute_preimage, create_atom
from jamp_1c.integration import to_jamp_envelope
from jamp_1c.tokenizer import BSLTokenizationError, canonicalize_bsl_query

SOURCE = "1c://conf-sha256:" + "a" * 64 + "/Catalog.Номенклатура"

def test_comments_are_removed_but_string_markers_survive() -> None:
    query = 'выбрать // remove\n "x // keep /* keep */" из T /* remove */ где A = 1'
    assert canonicalize_bsl_query(query) == 'ВЫБРАТЬ "x // keep /* keep */" ИЗ T ГДЕ A = 1'

def test_keyword_normalization_does_not_modify_identifiers_or_strings() -> None:
    query = 'выбрать выбраться "выбрать" из T'
    assert canonicalize_bsl_query(query) == 'ВЫБРАТЬ выбраться "выбрать" ИЗ T'

def test_span_and_telemetry_are_not_identity_inputs() -> None:
    base = {"extension_name": "", "module_type": "CommonModule", "method_name": "Run", "span_start": 10, "span_end": 20, "wall_ms": 12.5, "tempdb_bytes": 999}
    other = {"extension_name": "", "module_type": "CommonModule", "method_name": "Run", "span_start": 500, "span_end": 510, "wall_ms": 88.0, "tempdb_bytes": 123456}
    kwargs = {"source_ref": SOURCE, "atom_type": "observation", "operator_id": "ai:test", "operator_version": "v1", "content": {"kind": "bsl_query", "payload": "ВЫБРАТЬ A ИЗ T"}}
    assert compute_preimage(params=base, **kwargs) == compute_preimage(params=other, **kwargs)

def test_unknown_identity_keys_are_ignored() -> None:
    params = {"extension_name": "", "module_type": "CommonModule", "method_name": "Run"}
    extended = {**params, "session_id": "noise", "runtime_ms": 12}
    kwargs = {"source_ref": SOURCE, "atom_type": "hypothesis", "operator_id": "ai:test", "operator_version": "v1", "content": {"kind": "extension_patch", "payload": "diff"}}
    assert compute_preimage(params=params, **kwargs) == compute_preimage(params=extended, **kwargs)

def test_malformed_lexical_input_fails_closed() -> None:
    with pytest.raises(BSLTokenizationError):
        canonicalize_bsl_query('ВЫБРАТЬ "unterminated')
    with pytest.raises(BSLTokenizationError):
        canonicalize_bsl_query("ВЫБРАТЬ A ИЗ T " + chr(47) + chr(42) + " unterminated")

def test_hash_is_deterministic_and_envelope_preserves_domain_id() -> None:
    content = {"kind": "bsl_query", "payload": "выбрать A из T"}
    context = {"extension_name": "", "module_type": "CommonModule", "method_name": "Run", "span_start": 1, "span_end": 2}
    atom = create_atom(source_ref=SOURCE, atom_type="observation", operator_id="ai:test", operator_version="v1", content=content, context=context)
    preimage = compute_preimage(source_ref=SOURCE, atom_type="observation", operator_id="ai:test", operator_version="v1", content=content, params=context)
    assert atom.id == hashlib.sha256(preimage.encode("utf-8")).hexdigest()
    envelope = to_jamp_envelope(atom)
    assert envelope.content["jamp_1c_id"] == atom.id

def test_frozen_core_run_hash_is_unchanged() -> None:
    root = Path(__file__).resolve().parents[3]
    run_path = root / "src" / "jamp" / "run.py"
    actual = subprocess.check_output(["git", "hash-object", str(run_path)], text=True).strip()
    assert actual == "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
