"""Executable acceptance and adversarial contract for P20.8.

The tests are intentionally behavioral: each frozen gate must exercise a
specific invariant rather than merely naming the gate.
"""

import dataclasses
import json
import re

import pytest

from jamp.research.execution import (
    ExecutionIntegrityError,
    ExecutionRecord,
    make_execution,
)


GATES = [
    "schema_validity", "immutable_execution_record", "valid_execution_hash",
    "deterministic_execution_identity", "self_verification", "explicit_plan_hash",
    "explicit_question_hash", "explicit_execution_parameters", "explicit_observed_outputs",
    "runtime_independent_identity", "referenced_plan_exists", "unknown_plan_rejected",
    "plan_integrity_verified", "referenced_question_exists", "unknown_question_rejected",
    "question_integrity_verified", "plan_question_substitution_rejected",
    "complete_upstream_provenance", "raw_observation_distinguished_from_interpretation",
    "observations_immutable", "parameters_immutable", "candidate_outcomes_not_facts",
    "empty_observation_semantics", "deterministic_observation_order",
    "measurement_metadata_content_addressed", "post_hoc_observation_modification_rejected",
    "actual_outcome_may_differ_from_candidate", "deterministic_result_hash",
    "result_binds_execution_provenance", "trace_identity_preserved", "state_anchors_preserved",
    "result_substitution_rejected", "full_chain_reconstructible", "payload_tampering_detected",
    "observation_tampering_detected", "plan_substitution_rejected", "runtime_metadata_rejected",
    "retrospective_parameter_rewriting_rejected", "cross_runtime_reproduction",
    "zero_io_network_domain_contamination",
]


def test_gate_01_schema_validity():
    e = make_execution(plan_hash="p", question_hash="q", parameters={"x": 1}, observations=[])
    assert e.verify()


def test_gate_02_immutable_execution_record():
    e = make_execution("p", "q", {"x": 1}, [{"value": 2}])
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        e.plan_hash = "x"


def test_gate_03_valid_execution_hash():
    e = make_execution("p", "q", {"x": 1}, [])
    assert e.execution_hash == e.compute_hash()


def test_gate_04_deterministic_execution_identity():
    a = make_execution("p", "q", {"b": 2, "a": 1}, [{"v": 3}])
    b = make_execution("p", "q", {"a": 1, "b": 2}, [{"v": 3}])
    assert a.execution_hash == b.execution_hash


def test_gate_05_self_verification():
    e = make_execution("p", "q", {}, [])
    assert e.verify()
    bad = dataclasses.replace(e, execution_hash="0" * 64)
    with pytest.raises(ExecutionIntegrityError):
        bad.verify()


def test_gate_06_explicit_plan_hash():
    with pytest.raises(ValueError):
        make_execution("", "q", {}, [])


def test_gate_07_explicit_question_hash():
    with pytest.raises(ValueError):
        make_execution("p", "", {}, [])


def test_gate_08_explicit_execution_parameters():
    with pytest.raises(ValueError):
        make_execution("p", "q", None, [])


def test_gate_09_explicit_observed_outputs():
    e = make_execution("p", "q", {}, [])
    assert e.observations == ()


def test_gate_10_runtime_independent_identity():
    e = make_execution("p", "q", {"x": 1}, [])
    exported = e.export()
    assert not any(k in json.dumps(exported).lower() for k in ("timestamp", "pid", "hostname", "memory_address"))


def test_gate_11_referenced_plan_exists():
    e = make_execution("p", "q", {}, [], registry={"plans": {"p": {"plan_hash": "p"}}, "questions": {"q": {"question_hash": "q"}}})
    assert e.verify()


def test_gate_12_unknown_plan_rejected():
    e = make_execution("p", "q", {}, [], registry={"plans": {}, "questions": {"q": {"question_hash": "q"}}})
    with pytest.raises(ExecutionIntegrityError): e.verify()


def test_gate_13_plan_integrity_verified():
    reg = {"plans": {"p": {"plan_hash": "wrong"}}, "questions": {"q": {"question_hash": "q"}}}
    with pytest.raises(ExecutionIntegrityError): make_execution("p", "q", {}, [], registry=reg).verify()


def test_gate_14_referenced_question_exists():
    e = make_execution("p", "q", {}, [], registry={"plans": {"p": {"plan_hash": "p"}}, "questions": {"q": {"question_hash": "q"}}})
    assert e.verify()


def test_gate_15_unknown_question_rejected():
    reg = {"plans": {"p": {"plan_hash": "p"}}, "questions": {}}
    with pytest.raises(ExecutionIntegrityError): make_execution("p", "q", {}, [], registry=reg).verify()


def test_gate_16_question_integrity_verified():
    reg = {"plans": {"p": {"plan_hash": "p"}}, "questions": {"q": {"question_hash": "wrong"}}}
    with pytest.raises(ExecutionIntegrityError): make_execution("p", "q", {}, [], registry=reg).verify()


def test_gate_17_plan_question_substitution_rejected():
    reg = {"plans": {"p": {"plan_hash": "p", "question_hash": "other"}}, "questions": {"q": {"question_hash": "q"}}}
    with pytest.raises(ExecutionIntegrityError): make_execution("p", "q", {}, [], registry=reg).verify()


def test_gate_18_complete_upstream_provenance():
    reg = {"plans": {"p": {"plan_hash": "p", "question_hash": "q", "provenance": {"x": 1}}}, "questions": {"q": {"question_hash": "q", "provenance": {"root": "o"}}}}
    e = make_execution("p", "q", {}, [], registry=reg)
    assert e.upstream_provenance["plan_hash"] == "p"


def test_gate_19_raw_observation_distinguished_from_interpretation():
    e = make_execution("p", "q", {}, [{"value": 1, "interpretation": "ignored"}])
    assert e.observations[0]["value"] == 1
    assert "interpretation" not in e.observations[0]


def test_gate_20_observations_immutable():
    e = make_execution("p", "q", {}, [{"value": 1}])
    with pytest.raises(TypeError): e.observations[0]["value"] = 2


def test_gate_21_parameters_immutable():
    e = make_execution("p", "q", {"x": 1}, [])
    with pytest.raises(TypeError): e.parameters["x"] = 2


def test_gate_22_candidate_outcomes_not_facts():
    e = make_execution("p", "q", {"candidate_outcomes": ["yes"]}, [{"value": "no"}])
    assert e.observations[0]["value"] == "no"


def test_gate_23_empty_observation_semantics():
    e = make_execution("p", "q", {}, [])
    assert e.observations == () and e.observation_status == "EMPTY"


def test_gate_24_deterministic_observation_order():
    a = make_execution("p", "q", {}, [{"id": "b"}, {"id": "a"}])
    b = make_execution("p", "q", {}, [{"id": "a"}, {"id": "b"}])
    assert [x["id"] for x in a.observations] == ["b", "a"]
    assert a.execution_hash != b.execution_hash


def test_gate_25_measurement_metadata_content_addressed():
    e = make_execution("p", "q", {}, [{"value": 1, "metadata": {"instrument": "A"}}])
    assert re.fullmatch(r"[0-9a-f]{64}", e.observations[0]["measurement_metadata_hash"])


def test_gate_26_post_hoc_observation_modification_rejected():
    e = make_execution("p", "q", {}, [{"value": 1}])
    bad = dataclasses.replace(e, observations=({"value": 2},))
    with pytest.raises(ExecutionIntegrityError): bad.verify()


def test_gate_27_actual_outcome_may_differ_from_candidate():
    e = make_execution("p", "q", {"candidate_outcomes": ["A"]}, [{"value": "B"}])
    assert e.observations[0]["value"] == "B"


def test_gate_28_deterministic_result_hash():
    a = make_execution("p", "q", {}, [{"value": 1}])
    b = make_execution("p", "q", {}, [{"value": 1}])
    assert a.result_hash == b.result_hash


def test_gate_29_result_binds_execution_provenance():
    e = make_execution("p", "q", {}, [])
    assert e.result_provenance["execution_hash"] == e.execution_hash


def test_gate_30_trace_identity_preserved():
    e = make_execution("p", "q", {}, [], trace_hash="t" * 64)
    assert e.trace_hash == "t" * 64


def test_gate_31_state_anchors_preserved():
    e = make_execution("p", "q", {}, [], state_hash="s" * 64)
    assert e.state_hash == "s" * 64


def test_gate_32_result_substitution_rejected():
    e = make_execution("p", "q", {}, [])
    bad = dataclasses.replace(e, result_hash="0" * 64)
    with pytest.raises(ExecutionIntegrityError): bad.verify()


def test_gate_33_full_chain_reconstructible():
    e = make_execution("p", "q", {}, [{"value": 1}], trace_hash="t" * 64, state_hash="s" * 64)
    chain = e.provenance_chain
    assert chain[:2] == ("q", "p")
    assert chain[-3:] == (e.result_hash, "t" * 64, "s" * 64)


def test_gate_34_payload_tampering_detected():
    e = make_execution("p", "q", {}, [])
    bad = dataclasses.replace(e, parameters={"tampered": True})
    with pytest.raises(ExecutionIntegrityError): bad.verify()


def test_gate_35_observation_tampering_detected():
    e = make_execution("p", "q", {}, [{"value": 1}])
    bad = dataclasses.replace(e, observations=({"value": 999},))
    with pytest.raises(ExecutionIntegrityError): bad.verify()


def test_gate_36_plan_substitution_rejected():
    e = make_execution("p", "q", {}, [])
    bad = dataclasses.replace(e, plan_hash="other")
    with pytest.raises(ExecutionIntegrityError): bad.verify()


def test_gate_37_runtime_metadata_rejected():
    with pytest.raises(ValueError): make_execution("p", "q", {"pid": 12}, [])


def test_gate_38_retrospective_parameter_rewriting_rejected():
    e = make_execution("p", "q", {"x": 1}, [])
    rewritten = dataclasses.replace(e, parameters={"x": 2})
    assert rewritten.execution_hash != e.execution_hash
    with pytest.raises(ExecutionIntegrityError): rewritten.verify()


def test_gate_39_cross_runtime_reproduction():
    a = make_execution("p", "q", {"b": 2, "a": 1}, [{"value": 3}])
    assert a.execution_hash == make_execution("p", "q", {"a": 1, "b": 2}, [{"value": 3}]).execution_hash


def test_gate_40_zero_io_network_domain_contamination():
    import inspect
    source = inspect.getsource(__import__("jamp.research.execution", fromlist=["x"]))
    assert not re.search(r"(^|\n)\s*(import|from)\s+(requests|urllib|socket|subprocess|jamp\.domain)\b", source)


def test_all_40_gates_are_present_and_executable():
    assert len(GATES) == 40
    for i in range(1, 41):
        assert f"test_gate_{i:02d}_" in __import__(__name__, fromlist=["x"]).__dict__
