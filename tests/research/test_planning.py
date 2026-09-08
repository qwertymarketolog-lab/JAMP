"""P20.7 Research Planning Engine — executable acceptance contract.

The tests are intentionally behavioral: each frozen gate must execute against the
research planning API rather than merely declaring a gate name.
"""

import hashlib
import json

import pytest

from jamp.research.planning import (
    PlanningError,
    PlanningStatus,
    PlanningStrategy,
    compute_plan_hash,
    make_plan,
)


GATES = range(1, 37)


def _base_question():
    return {"question_hash": "q-001", "status": "GAP", "formulation": "Which trace discriminates A from B?"}


def _base_evidence():
    return {"result_hash": "r-001", "claim_hash": "c-001", "status": "SUPPORTED"}


def _registry():
    return {
        "questions": {"q-001": _base_question()},
        "evidence": {"r-001": _base_evidence()},
        "claims": {"c-001": {"claim_hash": "c-001", "status": "SUPPORTED", "evidence_refs": ["r-001"]}},
    }


def _plan(**overrides):
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
    return make_plan(registry=_registry(), **payload)


def _tamper(record, **changes):
    data = record.export()
    data.update(changes)
    return data


# 01 Schema validity
def test_gate_01_schema_validity():
    p = _plan()
    assert p.verify() is True


# 02 Immutable planning record
def test_gate_02_immutable_planning_record():
    p = _plan()
    with pytest.raises((TypeError, AttributeError)):
        p.objective = "changed"


# 03 Valid plan_hash
def test_gate_03_valid_plan_hash():
    p = _plan()
    assert p.plan_hash == compute_plan_hash(p.export())


# 04 Deterministic hash computation
def test_gate_04_deterministic_hash_computation():
    a, b = _plan(), _plan()
    assert a.plan_hash == b.plan_hash


# 05 Self-verification
def test_gate_05_self_verification():
    assert _plan().verify()


# 06 Canonical objective
def test_gate_06_canonical_objective():
    with pytest.raises(PlanningError):
        _plan(objective=" ")


# 07 Explicit planning strategy/type
def test_gate_07_explicit_strategy():
    with pytest.raises(PlanningError):
        _plan(strategy="")


# 08 Valid plan status
def test_gate_08_valid_status():
    with pytest.raises(PlanningError):
        _plan(status="UNKNOWN")


# 09 Runtime-independent identity
def test_gate_09_runtime_independent_identity():
    p = _plan()
    assert all(k not in p.export() for k in ("timestamp", "uuid", "pid", "hostname", "environment"))


# 10 Only registered questions/evidence
def test_gate_10_registered_refs_only():
    with pytest.raises(PlanningError):
        _plan(question_refs=["unknown"])


# 11 Unknown question rejected
def test_gate_11_unknown_question_rejected():
    with pytest.raises(PlanningError):
        _plan(question_refs=["q-404"])


# 12 Question integrity verified
def test_gate_12_question_integrity_verified():
    registry = _registry()
    registry["questions"]["q-001"]["question_hash"] = "tampered"
    with pytest.raises(PlanningError):
        make_plan(registry=registry, objective="x", strategy="GAP", status="CANDIDATE", question_refs=["q-001"])


# 13 Evidence integrity verified
def test_gate_13_evidence_integrity_verified():
    registry = _registry()
    registry["evidence"]["r-001"]["result_hash"] = "tampered"
    with pytest.raises(PlanningError):
        make_plan(registry=registry, objective="x", strategy="GAP", status="CANDIDATE", evidence_refs=["r-001"])


# 14 Claim integrity verified
def test_gate_14_claim_integrity_verified():
    registry = _registry()
    registry["claims"]["c-001"]["claim_hash"] = "tampered"
    with pytest.raises(PlanningError):
        _plan(registry=registry)


# 15 Substitution attack rejected
def test_gate_15_substitution_rejected():
    with pytest.raises(PlanningError):
        _plan(evidence_refs=["r-001"], selection_rationale={"claim_refs": ["c-404"]})


# 16 Complete provenance preserved
def test_gate_16_complete_provenance_preserved():
    p = _plan()
    assert p.export()["question_refs"] == ["q-001"]
    assert p.export()["evidence_refs"] == ["r-001"]


# 17 Recursive provenance preserved
def test_gate_17_recursive_provenance_preserved():
    p = _plan()
    prov = p.provenance
    assert "questions" in prov and "evidence" in prov


# 18 Open question → candidate experiment mapping
def test_gate_18_open_question_mapping():
    assert _plan().candidate_experiment["question_hash"] == "q-001"


# 19 GAP → information acquisition design
def test_gate_19_gap_design():
    p = _plan(strategy=PlanningStrategy.GAP.value)
    assert p.candidate_experiment["purpose"] == "information_acquisition"


# 20 CONFLICTING → discriminating design
def test_gate_20_conflicting_design():
    p = _plan(strategy=PlanningStrategy.DISCRIMINATE.value)
    assert p.candidate_experiment["purpose"] == "discrimination"


# 21 UNRESOLVED → uncertainty-reducing design
def test_gate_21_unresolved_design():
    registry = _registry()
    registry["questions"]["q-001"]["status"] = "UNRESOLVED"
    p = _plan(registry=registry, strategy=PlanningStrategy.UNCERTAINTY_REDUCTION.value)
    assert p.candidate_experiment["purpose"] == "uncertainty_reduction"


# 22 ANSWERED question cannot silently become required experiment
def test_gate_22_answered_not_required():
    registry = _registry()
    registry["questions"]["q-001"]["status"] = "ANSWERED"
    with pytest.raises(PlanningError):
        _plan(registry=registry)


# 23 Experiment objective explicitly represented
def test_gate_23_experiment_objective():
    assert _plan().experiment_objective


# 24 Inputs/conditions explicitly represented
def test_gate_24_conditions():
    assert _plan().export()["conditions"] == {"parameter": "X", "levels": ["A", "B"]}


# 25 Candidate outcomes explicitly represented
def test_gate_25_candidate_outcomes():
    assert _plan().export()["candidate_outcomes"] == ["trace_A", "trace_B"]


# 26 No empirical outcome asserted as fact
def test_gate_26_no_empirical_assertion():
    with pytest.raises(PlanningError):
        _plan(candidate_outcomes=["The experiment proves A is true"])


# 27 Deterministic candidate generation
def test_gate_27_candidate_generation_deterministic():
    assert _plan().candidate_experiment == _plan().candidate_experiment


# 28 Deterministic candidate ranking/selection
def test_gate_28_selection_deterministic():
    a = _plan(selection_rationale={"basis": "reduces unresolved uncertainty", "question_refs": ["q-001"]})
    b = _plan(selection_rationale={"question_refs": ["q-001"], "basis": "reduces unresolved uncertainty"})
    assert a.plan_hash == b.plan_hash


# 29 Equivalent plans produce identical hash
def test_gate_29_equivalent_hash():
    assert _plan().plan_hash == _plan().plan_hash


# 30 Distinct experimental designs cannot silently collapse
def test_gate_30_distinct_designs_distinct_hash():
    assert _plan(conditions={"parameter": "X", "levels": ["A", "B"]}).plan_hash != _plan(conditions={"parameter": "Y", "levels": ["A", "B"]}).plan_hash


# 31 Selection rationale is provenance-addressed
def test_gate_31_rationale_provenance():
    assert _plan().selection_rationale["question_refs"] == ["q-001"]


# 32 Plan payload tampering detected
def test_gate_32_plan_tampering():
    p = _plan()
    bad = _tamper(p, objective="tampered")
    assert bad["plan_hash"] != compute_plan_hash(bad)


# 33 Question/evidence substitution rejected
def test_gate_33_question_evidence_substitution():
    with pytest.raises(PlanningError):
        _plan(evidence_refs=["r-404"])


# 34 Runtime metadata injection rejected
def test_gate_34_runtime_metadata_injection():
    with pytest.raises(PlanningError):
        _plan(runtime_metadata={"pid": 123})


# 35 Cross-runtime byte-identical reproduction
def test_gate_35_cross_runtime_bytes():
    a = _plan().export()
    b = _plan().export()
    assert json.dumps(a, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(b, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# 36 Zero IO/network/domain contamination
def test_gate_36_zero_contamination():
    import inspect
    import jamp.research.planning as module
    source = inspect.getsource(module)
    assert "jamp.domain" not in source
    assert "requests" not in source
    assert "urllib" not in source
    assert "open(" not in source


assert len(list(GATES)) == 36
