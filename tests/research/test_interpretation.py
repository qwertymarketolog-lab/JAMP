from __future__ import annotations
import hashlib, inspect, json
import pytest
from jamp.research.interpretation import InterpretationClassification, InterpretationIntegrityError, InterpretationRecord, make_interpretation
class ResultStub:
    def __init__(self, result_hash="result-1", execution_hash="execution-1", question_hash="question-1", plan_hash="plan-1", trace_hash="trace-1", state_hash="state-1"):
        self.result_hash=result_hash; self.execution_hash=execution_hash; self.question_hash=question_hash; self.plan_hash=plan_hash; self.trace_hash=trace_hash; self.state_hash=state_hash
    def verify(self): return True
def registry(result=None):
    r=result or ResultStub(); return {r.result_hash:r}
def base(**kw):
    d=dict(result_hash="result-1", analytical_target={"hypothesis_hash":"hyp-1","question_hash":"question-1"}, method="comparative", parameters={"model":"A","threshold":0.5}, conclusion="Observed result supports target.", classification=InterpretationClassification.SUPPORTS, evidence={"observations":[1,2,3]}); d.update(kw); return d

def test_01_schema_validity(): assert isinstance(make_interpretation(**base(),registry=registry()),InterpretationRecord)
def test_02_immutable_record():
    x=make_interpretation(**base(),registry=registry())
    with pytest.raises((AttributeError,TypeError)): x.conclusion="x"
def test_03_valid_hash(): assert len(make_interpretation(**base(),registry=registry()).interpretation_hash)==64
def test_04_deterministic_identity(): assert make_interpretation(**base(),registry=registry()).interpretation_hash==make_interpretation(**base(),registry=registry()).interpretation_hash
def test_05_self_verification(): assert make_interpretation(**base(),registry=registry()).verify(registry())
def test_06_explicit_result_binding(): assert make_interpretation(**base(),registry=registry()).result_hash=="result-1"
def test_07_explicit_analytical_target(): assert make_interpretation(**base(),registry=registry()).analytical_target["hypothesis_hash"]=="hyp-1"
def test_08_explicit_method(): assert make_interpretation(**base(),registry=registry()).method=="comparative"
def test_09_explicit_parameters(): assert make_interpretation(**base(),registry=registry()).parameters["model"]=="A"
def test_10_runtime_independent_identity(): assert "timestamp" not in make_interpretation(**base(),registry=registry()).export()
def test_11_result_must_exist():
    with pytest.raises(InterpretationIntegrityError): make_interpretation(**base(result_hash="x"),registry=registry())
def test_12_unknown_hash_rejected(): test_11_result_must_exist()
def test_13_result_integrity_verified():
    class Bad(ResultStub):
        def verify(self): return False
    with pytest.raises(InterpretationIntegrityError): make_interpretation(**base(),registry=registry(Bad()))
def test_14_execution_provenance(): assert make_interpretation(**base(),registry=registry()).execution_hash=="execution-1"
def test_15_question_plan_provenance():
    x=make_interpretation(**base(),registry=registry()); assert (x.question_hash,x.plan_hash)==("question-1","plan-1")
def test_16_trace_state_anchors():
    x=make_interpretation(**base(),registry=registry()); assert (x.trace_hash,x.state_hash)==("trace-1","state-1")
def test_17_result_substitution():
    x=make_interpretation(**base(),registry=registry()); object.__setattr__(x,"result_hash","other")
    with pytest.raises(InterpretationIntegrityError): x.verify(registry())
def test_18_recursive_provenance_preserved(): assert len(make_interpretation(**base(),registry=registry()).provenance_chain())==6
def test_19_result_is_not_interpretation(): assert make_interpretation(**base(),registry=registry()).conclusion != "result"
def test_20_explicit_conclusion(): assert make_interpretation(**base(),registry=registry()).conclusion
def test_21_supports(): assert make_interpretation(**base(classification="SUPPORTS"),registry=registry()).classification is InterpretationClassification.SUPPORTS
def test_22_refutes(): assert make_interpretation(**base(classification="REFUTES"),registry=registry()).classification is InterpretationClassification.REFUTES
def test_23_undetermined(): assert make_interpretation(**base(classification="UNDETERMINED"),registry=registry()).classification is InterpretationClassification.UNDETERMINED
def test_24_contradictory_preserved():
    a=make_interpretation(**base(classification="SUPPORTS"),registry=registry()); b=make_interpretation(**base(classification="REFUTES"),registry=registry()); assert a.interpretation_hash!=b.interpretation_hash
def test_25_multiple_models_preserved():
    a=make_interpretation(**base(parameters={"model":"A"}),registry=registry()); b=make_interpretation(**base(parameters={"model":"B"}),registry=registry()); assert a.interpretation_hash!=b.interpretation_hash
def test_26_no_hypothesis_promotion(): assert not hasattr(make_interpretation(**base(),registry=registry()),"hypothesis_status")
def test_27_no_claim_creation(): assert not hasattr(make_interpretation(**base(),registry=registry()),"claim_hash")
def test_28_no_unsupported_status():
    with pytest.raises(InterpretationIntegrityError): make_interpretation(**base(classification="SUPPORTED"),registry=registry())
def test_29_canonical_parameters():
    a=make_interpretation(**base(parameters={"b":2,"a":1}),registry=registry()); b=make_interpretation(**base(parameters={"a":1,"b":2}),registry=registry()); assert a.interpretation_hash==b.interpretation_hash
def test_30_deterministic_hash(): assert make_interpretation(**base(),registry=registry()).interpretation_hash==make_interpretation(**base(),registry=registry()).interpretation_hash
def test_31_equivalent_same_hash(): test_30_deterministic_hash()
def test_32_material_difference_distinct():
    a=make_interpretation(**base(method="m1"),registry=registry()); b=make_interpretation(**base(method="m2"),registry=registry()); assert a.interpretation_hash!=b.interpretation_hash
def test_33_content_addressed_provenance():
    x=make_interpretation(**base(),registry=registry()); assert x.interpretation_hash==hashlib.sha256(json.dumps(x.canonical_payload(),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def test_34_deterministic_export_order(): assert list(make_interpretation(**base(),registry=registry()).export())==list(make_interpretation(**base(),registry=registry()).export())
def test_35_payload_tampering():
    x=make_interpretation(**base(),registry=registry()); object.__setattr__(x,"conclusion","tampered")
    with pytest.raises(InterpretationIntegrityError): x.verify(registry())
def test_36_result_substitution_attack(): test_17_result_substitution()
def test_37_target_substitution_detected():
    x=make_interpretation(**base(),registry=registry()); object.__setattr__(x,"analytical_target",{"hypothesis_hash":"other"})
    with pytest.raises(InterpretationIntegrityError): x.verify(registry())
def test_38_runtime_metadata_injection():
    with pytest.raises(InterpretationIntegrityError): make_interpretation(**base(parameters={"timestamp":"now"}),registry=registry())
def test_39_cross_runtime_byte_identical(): assert make_interpretation(**base(),registry=registry()).export()==make_interpretation(**base(),registry=registry()).export()
def test_40_zero_io_network_domain_contamination():
    src=inspect.getsource(__import__("jamp.research.interpretation",fromlist=["x"])); assert "jamp.domain" not in src and "requests" not in src and "urllib" not in src and "open(" not in src
