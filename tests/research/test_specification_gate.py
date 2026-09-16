from __future__ import annotations

import hashlib

from jamp.research.canonical import canonical_bytes
from jamp.research.specification_gate import (
    GateStatus,
    MappingArtifactSource,
    SpecificationGate,
    SpecificationRef,
)


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _criterion(*, overlap: bool = False, self_test_failure: bool = False) -> tuple[str, dict]:
    if overlap:
        acceptance = {"field": "x", "op": "in", "value": [1, 2]}
        rejection = {"field": "x", "op": "in", "value": [2, 3]}
        pass_sample, fail_sample = 1, 3
    else:
        acceptance = {"field": "x", "op": "eq", "value": 2}
        rejection = {"field": "x", "op": "eq", "value": 3}
        pass_sample, fail_sample = (3, 3) if self_test_failure else (2, 3)
    inconclusive = {"field": "x", "op": "eq", "value": 0}
    criterion = {
        "criterion_id": "criterion-1",
        "criterion_version": "0",
        "hypothesis_ref": "hypothesis-1",
        "prediction_ref": "prediction-1",
        "preconditions": [],
        "observation_schema": {"x": "integer"},
        "acceptance_predicate": acceptance,
        "rejection_predicate": rejection,
        "inconclusive_predicate": inconclusive,
        "self_test": {
            "pass_case": {"sample": {"x": pass_sample}, "expected": "FAIL" if self_test_failure else "PASS"},
            "fail_case": {"sample": {"x": fail_sample}, "expected": "FAIL"},
            "inconclusive_case": {"sample": {"x": 0}, "expected": "INCONCLUSIVE"},
        },
        "provenance_reference": "authoring-1",
        "covered_domain": [{"x": 0}, {"x": pass_sample}, {"x": 2}, {"x": fail_sample}],
    }
    criterion_hash = _digest(criterion)
    return criterion_hash, {**criterion, "criterion_hash": criterion_hash}


def _source(*, overlap: bool = False, self_test_failure: bool = False, bad_spec_hash: bool = False) -> tuple[MappingArtifactSource, SpecificationRef]:
    criterion_hash, criterion = _criterion(overlap=overlap, self_test_failure=self_test_failure)
    aggregation = {"version": "0", "mode": "deterministic"}
    aggregation_hash = _digest(aggregation)
    criterion_set = {
        "set_id": "set-1",
        "version": "0",
        "criteria": [criterion_hash],
        "aggregation_rule_ref": aggregation_hash,
        "provenance_reference": "authoring-1",
    }
    criterion_set_hash = _digest(criterion_set)
    criterion_set["criterion_set_hash"] = criterion_set_hash
    specification = {
        "spec_id": "spec-1",
        "spec_version": "0",
        "hypothesis_ref": "hypothesis-1",
        "prediction_ref": "prediction-1",
        "criterion_set_ref": criterion_set_hash,
        "frozen_at": "2026-09-16T00:00:00Z",
    }
    spec_hash = _digest(specification)
    declared_spec_hash = "0" * 64 if bad_spec_hash else spec_hash
    specification["spec_hash"] = declared_spec_hash
    source = MappingArtifactSource(
        specifications={declared_spec_hash: specification},
        criterion_sets={criterion_set_hash: criterion_set},
        criteria={criterion_hash: criterion},
        aggregation_rules={aggregation_hash: aggregation},
    )
    return source, SpecificationRef("spec-1", "0", declared_spec_hash)


def test_ce01_happy_path_passes_gate() -> None:
    source, ref = _source()
    result = SpecificationGate(source).run_gate(ref)
    assert result.status is GateStatus.PASS
    assert result.diagnostics == ()


def test_ce02_hash_mismatch_fails_closed() -> None:
    source, ref = _source(bad_spec_hash=True)
    result = SpecificationGate(source).run_gate(ref)
    assert result.status is GateStatus.FAIL
    assert [item.code for item in result.diagnostics] == ["HASH_MISMATCH"]


def test_ce03_predicate_overlap_fails_closed() -> None:
    source, ref = _source(overlap=True)
    result = SpecificationGate(source).run_gate(ref)
    assert result.status is GateStatus.FAIL
    assert [item.code for item in result.diagnostics] == ["PREDICATE_OVERLAP"]


def test_ce04_self_test_failure_fails_closed() -> None:
    source, ref = _source(self_test_failure=True)
    result = SpecificationGate(source).run_gate(ref)
    assert result.status is GateStatus.FAIL
    assert [item.code for item in result.diagnostics] == ["SELF_TEST_FAILURE"]


def test_run_gate_has_no_experimental_input_parameter() -> None:
    import inspect

    parameters = inspect.signature(SpecificationGate.run_gate).parameters
    assert tuple(parameters) == ("self", "spec_ref")
