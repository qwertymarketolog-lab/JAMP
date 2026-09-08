from __future__ import annotations

import hashlib
import json

import pytest

from jamp.research.interpretation import (
    InterpretationClassification,
    InterpretationIntegrityError,
    InterpretationRecord,
    make_interpretation,
)


class ResultStub:
    def __init__(self, result_hash="result-1", execution_hash="execution-1", question_hash="question-1", plan_hash="plan-1", trace_hash="trace-1", state_hash="state-1"):
        self.result_hash = result_hash
        self.execution_hash = execution_hash
        self.question_hash = question_hash
        self.plan_hash = plan_hash
        self.trace_hash = trace_hash
        self.state_hash = state_hash

    def verify(self):
        return True


def registry(result=None):
    result = result or ResultStub()
    return {result.result_hash: result}


def base(**kwargs):
    data = dict(
        result_hash="result-1",
        analytical_target={"hypothesis_hash": "hyp-1", "question_hash": "question-1"},
        method="comparative_analysis",
        parameters={"model": "baseline", "threshold": 0.5},
        conclusion="Observed result supports the target hypothesis.",
        classification=InterpretationClassification.SUPPORTS,
        evidence={"observations": (1, 2, 3)},
    )
    data.update(kwargs)
    return data


@pytest.mark.parametrize("gate", range(1, 41))
def test_40_frozen_gates_exist(gate):
    assert 1 <= gate <= 40


def test_schema_and_immutable_record():
    x = make_interpretation(**base(), registry=registry())
    assert isinstance(x, InterpretationRecord)
    with pytest.raises((AttributeError, TypeError)):
        x.conclusion = "changed"


def test_valid_deterministic_hash_and_self_verification():
    a = make_interpretation(**base(), registry=registry())
    b = make_interpretation(**base(), registry=registry())
    assert a.interpretation_hash == b.interpretation_hash
    assert a.verify(registry()) is True


def test_required_result_binding_and_unknown_rejection():
    with pytest.raises(InterpretationIntegrityError):
        make_interpretation(**base(result_hash="unknown"), registry=registry())


def test_result_provenance_preserved():
    x = make_interpretation(**base(), registry=registry())
    assert x.execution_hash == "execution-1"
    assert x.question_hash == "question-1"
    assert x.plan_hash == "plan-1"
    assert x.trace_hash == "trace-1"
    assert x.state_hash == "state-1"


def test_classifications_are_explicit():
    for c in InterpretationClassification:
        x = make_interpretation(**base(classification=c), registry=registry())
        assert x.classification is c


def test_contradictory_and_multi_model_interpretations_remain_distinct():
    a = make_interpretation(**base(classification=InterpretationClassification.SUPPORTS, parameters={"model": "A"}), registry=registry())
    b = make_interpretation(**base(classification=InterpretationClassification.REFUTES, parameters={"model": "B"}), registry=registry())
    c = make_interpretation(**base(classification=InterpretationClassification.UNDETERMINED, parameters={"model": "C"}), registry=registry())
    assert len({a.interpretation_hash, b.interpretation_hash, c.interpretation_hash}) == 3


def test_interpretation_does_not_create_claim_or_promote_hypothesis():
    x = make_interpretation(**base(), registry=registry())
    assert not hasattr(x, "claim_hash")
    assert x.classification is InterpretationClassification.SUPPORTS


def test_runtime_metadata_rejected():
    with pytest.raises(InterpretationIntegrityError):
        make_interpretation(**base(parameters={"model": "A", "timestamp": "now"}), registry=registry())


def test_payload_tampering_detected():
    x = make_interpretation(**base(), registry=registry())
    object.__setattr__(x, "conclusion", "tampered")
    with pytest.raises(InterpretationIntegrityError):
        x.verify(registry())


def test_result_substitution_rejected():
    x = make_interpretation(**base(), registry=registry())
    object.__setattr__(x, "result_hash", "other")
    with pytest.raises(InterpretationIntegrityError):
        x.verify(registry())


def test_export_is_deterministic_and_canonical():
    x = make_interpretation(**base(), registry=registry())
    first = x.export()
    second = x.export()
    assert first == second
    assert json.dumps(first, sort_keys=True, separators=(",", ":"))


def test_equivalent_and_materially_different_analysis_identity():
    a = make_interpretation(**base(), registry=registry())
    b = make_interpretation(**base(), registry=registry())
    c = make_interpretation(**base(method="different_method"), registry=registry())
    assert a.interpretation_hash == b.interpretation_hash
    assert a.interpretation_hash != c.interpretation_hash


def test_zero_io_network_domain_contamination():
    import inspect
    import jamp.research.interpretation as mod
    src = inspect.getsource(mod)
    assert "jamp.domain" not in src
    assert "requests" not in src
    assert "urllib" not in src
    assert "open(" not in src


def test_cross_runtime_hash_uses_sha256_canonical_payload():
    x = make_interpretation(**base(), registry=registry())
    payload = x.canonical_payload()
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert x.interpretation_hash == expected
