"""P20.7 Research Planning Engine — executable acceptance contract.

The tests are intentionally behavioral: each frozen gate must execute against the
research planning API rather than merely declaring a gate name.
"""

import json
import pytest

from jamp.research.planning import PlanningError, PlanningStatus, PlanningStrategy, compute_plan_hash, make_plan

GATES = range(1, 37)


def _base_question():
    return {"question_hash": "q-001", "status": "GAP", "formulation": "Which trace discriminates A from B?"}


def _base_evidence():
    return {"result_hash": "r-001", "claim_hash": "c-001", "status": "SUPPORTED"}


def _registry():
    return {"questions": {"q-001": _base_question()}, "evidence": {"r-001": _base_evidence()}, "claims": {"c-001": {"claim_hash": "c-001", "status": "SUPPORTED", "evidence_refs": ["r-001"]}}}


def _plan(**overrides):
    registry = overrides.pop("registry", None) or _registry()
    payload = {
        "objective": "Acquire observations that distinguish the unresolved alternatives.",
        "strategy": PlanningStrategy.DISCRIMINATE.value,
        "status": PlanningStatus.CANDIDATE.value,
        "question_refs": ["q-001"],
        "evidence_refs": ["r-001"],
        "conditions": {"parameter": "X", "levels": ["A", "B"]},
        "candidate_outcomes": ["trace_A", "trace_B"],
        "experiment_objective": "Observe whether the empirical trace differs between A and B.",
        "selection_rationale": {"basis": "reduces unresolved uncertainty", "question_refs": ["q-001"]},
        "hypothesis_refs": [],
    }
    payload.update(overrides)
    return make_plan(registry=registry, **payload)


def _tamper(record, **changes):
    data = dict(record.export())
    data.update(changes)
    return data


def test_gate_01_schema_validity(): assert _plan().verify() is True

def test_gate_02_immutable_planning_record():
    with pytest.raises((TypeError, AttributeError)): _plan().objective = "changed"

def test_gate_03_valid_plan_hash():
    p = _plan(); assert p.plan_hash == compute_plan_hash(p.export())

def test_gate_04_deterministic_hash_computation(): assert _plan().plan_hash == _plan().plan_hash

def test_gate_05_self_verification(): assert _plan().verify()

def test_gate_06_canonical_objective():
    with pytest.raises(PlanningError): _plan(objective=" ")

def test_gate_07_explicit_strategy():
    with pytest.raises(PlanningError): _plan(strategy="")

def test_gate_08_valid_status():
    with pytest.raises(PlanningError): _plan(status="UNKNOWN")

def test_gate_09_runtime_independent_identity():
    assert all(k not in _plan().export() for k in ("timestamp", "uuid", "pid", "hostname", "environment"))

def test_gate_10_registered_refs_only():
    with pytest.raises(PlanningError): _plan(question_refs=["unknown"])

def test_gate_11_unknown_question_rejected():
    with pytest.raises(PlanningError): _plan(question_refs=["q-404"])

def test_gate_12_question_integrity_verified():
    r = _registry(); r["questions"]["q-001"]["question_hash"] = "tampered"
    with pytest.raises(PlanningError): _plan(registry=r)

def test_gate_13_evidence_integrity_verified():
    r = _registry(); r["evidence"]["r-001"]["result_hash"] = "tampered"
    with pytest.raises(PlanningError): _plan(registry=r)

def test_gate_14_claim_integrity_verified():
    r = _registry(); r["claims"]["c-001"]["claim_hash"] = "tampered"
    with pytest.raises(PlanningError): _plan(registry=r, selection_rationale={"claim_refs": ["c-001"]})

def test_gate_15_substitution_rejected():
    with pytest.raises(PlanningError): _plan(selection_rationale={"claim_refs": ["c-404"]})

def test_gate_16_complete_provenance_preserved():
    p = _plan(); assert p.export()["question_refs"] == ["q-001"]; assert p.export()["evidence_refs"] == ["r-001"]

def test_gate_17_recursive_provenance_preserved():
    p = _plan(); assert "questions" in p.provenance and "evidence" in p.provenance

def test_gate_18_open_question_mapping(): assert _plan().candidate_experiment["question_hash"] == "q-001"

def test_gate_19_gap_design(): assert _plan(strategy=PlanningStrategy.GAP.value).candidate_experiment["purpose"] == "information_acquisition"

def test_gate_20_conflicting_design(): assert _plan(strategy=PlanningStrategy.DISCRIMINATE.value).candidate_experiment["purpose"] == "discrimination"

def test_gate_21_unresolved_design():
    r = _registry(); r["questions"]["q-001"]["status"] = "UNRESOLVED"
    assert _plan(registry=r, strategy=PlanningStrategy.UNCERTAINTY_REDUCTION.value).candidate_experiment["purpose"] == "uncertainty_reduction"

def test_gate_22_answered_not_required():
    r = _registry(); r["questions"]["q-001"]["status"] = "ANSWERED"
    with pytest.raises(PlanningError): _plan(registry=r)

def test_gate_23_experiment_objective(): assert _plan().experiment_objective

def test_gate_24_conditions(): assert _plan().export()["conditions"] == {"parameter": "X", "levels": ["A", "B"]}

def test_gate_25_candidate_outcomes(): assert _plan().export()["candidate_outcomes"] == ["trace_A", "trace_B"]

def test_gate_26_no_empirical_assertion():
    with pytest.raises(PlanningError): _plan(candidate_outcomes=["The experiment proves A is true"])

def test_gate_27_candidate_generation_deterministic(): assert _plan().candidate_experiment == _plan().candidate_experiment

def test_gate_28_selection_deterministic():
    a = _plan(selection_rationale={"basis": "reduces unresolved uncertainty", "question_refs": ["q-001"]})
    b = _plan(selection_rationale={"question_refs": ["q-001"], "basis": "reduces unresolved uncertainty"})
    assert a.plan_hash == b.plan_hash

def test_gate_29_equivalent_hash(): assert _plan().plan_hash == _plan().plan_hash

def test_gate_30_distinct_designs_distinct_hash():
    assert _plan(conditions={"parameter": "X", "levels": ["A", "B"]}).plan_hash != _plan(conditions={"parameter": "Y", "levels": ["A", "B"]}).plan_hash

def test_gate_31_rationale_provenance(): assert _plan().selection_rationale["question_refs"] == ["q-001"]

def test_gate_32_plan_tampering():
    p = _plan(); bad = _tamper(p, objective="tampered"); assert bad["plan_hash"] != compute_plan_hash(bad)

def test_gate_33_question_evidence_substitution():
    with pytest.raises(PlanningError): _plan(evidence_refs=["r-404"])

def test_gate_34_runtime_metadata_injection():
    with pytest.raises(PlanningError): _plan(runtime_metadata={"pid": 123})

def test_gate_35_cross_runtime_bytes():
    a = json.dumps(dict(_plan().export()), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    b = json.dumps(dict(_plan().export()), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert a == b

def test_gate_36_zero_contamination():
    import inspect
    import jamp.research.planning as module
    source = inspect.getsource(module)
    assert "jamp.domain" not in source and "requests" not in source and "urllib" not in source and "open(" not in source

assert len(list(GATES)) == 36
