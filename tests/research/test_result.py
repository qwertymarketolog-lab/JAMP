"""P19.4 contract gates for deterministic research-result projection."""

from __future__ import annotations

import inspect

import pytest

from jamp.research.canonical import replay_hash
from jamp.research.replay import ReplayTrace, compute_trace_hash
from jamp.research.result import (
    ResearchResult,
    ResultIntegrityError,
    ResultProvenanceError,
    ResultTypeError,
    compute_result_hash,
    project_result,
)


PROVENANCE = {
    "source": "experiment",
    "operation": "measurement",
    "version": "1",
}


def make_trace(*, event_ids=("a" * 64,), result_state="state") -> ReplayTrace:
    initial = replay_hash({"value": 0})
    resulting = replay_hash({"value": result_state})
    trace_hash = compute_trace_hash(initial, event_ids, resulting)
    return ReplayTrace(initial, tuple(event_ids), resulting, trace_hash)


def make_result(**kwargs) -> ResearchResult:
    trace = kwargs.pop("trace", make_trace())
    return project_result(
        trace,
        result_type=kwargs.pop("result_type", "measurement"),
        result_payload=kwargs.pop("result_payload", {"value": 42}),
        provenance=kwargs.pop("provenance", PROVENANCE),
    )


def test_gate_01_result_schema() -> None:
    result = make_result()
    assert isinstance(result, ResearchResult)
    assert isinstance(result.trace_hash, str)
    assert isinstance(result.result_type, str)
    assert isinstance(result.result_payload, dict)
    assert isinstance(result.provenance, dict)
    assert isinstance(result.result_hash, str) and len(result.result_hash) == 64


def test_gate_02_result_immutable() -> None:
    result = make_result()
    with pytest.raises((AttributeError, TypeError)):
        result.result_type = "finding"


def test_gate_03_canonical_payload() -> None:
    a = make_result(result_payload={"b": 2, "a": 1})
    b = make_result(result_payload={"a": 1, "b": 2})
    assert a.result_hash == b.result_hash


def test_gate_04_deterministic_result_hash() -> None:
    result = make_result()
    assert result.result_hash == compute_result_hash(
        result.trace_hash,
        result.result_type,
        result.result_payload,
        result.provenance,
    )


def test_gate_05_result_self_verification() -> None:
    assert make_result().verify_integrity() is True


def test_gate_06_trace_binding_requires_valid_trace_hash() -> None:
    bad_trace = ReplayTrace("0" * 64, (), "1" * 64, "not-a-hash")
    with pytest.raises(ResultIntegrityError):
        project_result(bad_trace, "measurement", {"value": 1}, PROVENANCE)


def test_gate_07_trace_tamper_breaks_identity() -> None:
    result = make_result()
    object.__setattr__(result, "trace_hash", "f" * 64)
    assert result.verify_integrity() is False
    with pytest.raises(ResultIntegrityError):
        result.verify()


def test_gate_08_result_type_tamper_breaks_identity() -> None:
    result = make_result()
    object.__setattr__(result, "result_type", "finding")
    assert result.verify_integrity() is False
    with pytest.raises(ResultIntegrityError):
        result.verify()


def test_gate_09_payload_tamper_breaks_identity() -> None:
    result = make_result()
    object.__setattr__(result, "result_payload", {"value": 99})
    assert result.verify_integrity() is False
    with pytest.raises(ResultIntegrityError):
        result.verify()


def test_gate_10_provenance_tamper_breaks_identity() -> None:
    result = make_result()
    object.__setattr__(result, "provenance", {"source": "tampered", "operation": "measurement", "version": "1"})
    assert result.verify_integrity() is False
    with pytest.raises(ResultIntegrityError):
        result.verify()


def test_gate_11_same_state_different_trace_yields_different_result() -> None:
    trace_a = make_trace(event_ids=("a" * 64,), result_state="same")
    trace_b = make_trace(event_ids=("b" * 64,), result_state="same")
    assert trace_a.resulting_state_hash == trace_b.resulting_state_hash
    assert trace_a.trace_hash != trace_b.trace_hash
    result_a = make_result(trace=trace_a)
    result_b = make_result(trace=trace_b)
    assert result_a.result_hash != result_b.result_hash


def test_gate_12_same_trace_same_result_is_identical() -> None:
    trace = make_trace()
    a = make_result(trace=trace)
    b = make_result(trace=trace)
    assert a == b
    assert a.result_hash == b.result_hash


def test_gate_13_input_order_independence_for_provenance() -> None:
    a = make_result(provenance={"source": "experiment", "operation": "measurement", "version": "1"})
    b = make_result(provenance={"version": "1", "source": "experiment", "operation": "measurement"})
    assert a.result_hash == b.result_hash


def test_gate_14_canonical_key_order_independence_for_payload() -> None:
    a = make_result(result_payload={"z": {"b": 2, "a": 1}, "a": 0})
    b = make_result(result_payload={"a": 0, "z": {"a": 1, "b": 2}})
    assert a.result_hash == b.result_hash


def test_gate_15_unknown_result_type_rejected() -> None:
    with pytest.raises(ResultTypeError):
        make_result(result_type="unknown-result-type")


def test_gate_16_invalid_provenance_rejected() -> None:
    with pytest.raises(ResultProvenanceError):
        make_result(provenance={"source": "experiment", "operation": "measurement"})


def test_gate_17_runtime_contamination_excluded_from_hash() -> None:
    contaminated = {**PROVENANCE, "timestamp": "2026-09-08T21:46:07Z"}
    with pytest.raises(ResultProvenanceError):
        make_result(provenance=contaminated)
    clean_a = make_result(provenance=PROVENANCE)
    clean_b = make_result(provenance={"version": "1", "operation": "measurement", "source": "experiment"})
    assert clean_a.result_hash == clean_b.result_hash


def test_gate_18_research_isolation() -> None:
    source = inspect.getsource(__import__("jamp.research.result", fromlist=["*"]))
    assert "jamp.domain" not in source
    assert "import socket" not in source
    assert "import requests" not in source
    assert "import sqlite3" not in source
    assert "open(" not in source
