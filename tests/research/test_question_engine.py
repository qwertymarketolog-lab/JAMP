"""P20.6 executable 34-gate acceptance/adversarial contract."""
from __future__ import annotations

import hashlib
import json
import pytest
from jamp.research.question_engine import (
    QuestionIntegrityError, QuestionStatus, QuestionType, ResearchQuestion,
    compute_question_hash, make_question, resolve_question,
)

H1="1"*64; H2="2"*64; H3="3"*64; C1="4"*64; C2="5"*64; T1="6"*64

class Evidence:
    def __init__(self, result_hash, status="SUPPORTED"):
        self.result_hash=result_hash; self.trace_hash=T1; self.event_ids=(H2,); self.state_anchors=(H3,H2); self.status=status
    def verify_integrity(self): return True
    def export(self): return {"result_hash":self.result_hash,"trace_hash":self.trace_hash,"event_ids":self.event_ids,"state_anchors":self.state_anchors,"status":self.status}

class Registry:
    def __init__(self,*items): self.items={x.result_hash:x for x in items}
    def contains(self,k): return k in self.items
    def get(self,k): return self.items[k]
    def verify(self,k): return self.get(k).verify_integrity()
    def snapshot(self): return dict(self.items)

class Claim:
    def __init__(self,h,refs,status="SUPPORTED"): self.claim_hash=h; self.evidence_refs=tuple(refs); self.status=status
    def verify(self,registry):
        for r in self.evidence_refs:
            if r not in registry.snapshot(): raise QuestionIntegrityError("claim evidence missing")
        return True
    def export(self): return {"claim_hash":self.claim_hash,"evidence_refs":self.evidence_refs,"status":self.status}

class Hypothesis:
    def __init__(self,h): self.hypothesis_hash=h
    def verify(self,registry=None): return True


def q(**kw):
    evidence=kw.pop("evidence",()); claims=kw.pop("claims",()); hypotheses=kw.pop("hypotheses",())
    reg=Registry(*(Evidence(h) for h in evidence))
    return make_question(reg, formulation=kw.pop("formulation","Why does X occur?"), question_type=kw.pop("question_type",QuestionType.EXPLANATORY), context=kw.pop("context",{"domain":"test"}), constraints=kw.pop("constraints",{"scope":"local"}), evidence_hashes=evidence, claim_hashes=tuple(c.claim_hash for c in claims), hypothesis_hashes=tuple(h.hypothesis_hash for h in hypotheses), claims=claims, hypotheses=hypotheses, **kw)

# 01
def test_gate_01_schema_validity():
    x=q(); assert isinstance(x,ResearchQuestion) and x.formulation=="Why does X occur?"
# 02
def test_gate_02_immutable_question_record():
    x=q()
    with pytest.raises((AttributeError,TypeError)): x.formulation="mutated"
# 03
def test_gate_03_valid_question_hash():
    x=q(); assert len(x.question_hash)==64 and x.verify()
# 04
def test_gate_04_deterministic_hash_computation():
    assert q(context={"b":2,"a":1},constraints={"z":[2,1],"a":"x"}).question_hash==q(context={"a":1,"b":2},constraints={"a":"x","z":[2,1]}).question_hash
# 05
def test_gate_05_self_verification(): assert q().verify() is True
# 06
def test_gate_06_canonical_formulation(): assert q(formulation="  Why   does\n X occur? ").question_hash==q().question_hash
# 07
def test_gate_07_explicit_question_type():
    with pytest.raises((QuestionIntegrityError,ValueError,TypeError)): make_question(Registry(),formulation="X?",question_type="",context={},constraints={})
# 08
def test_gate_08_valid_question_status():
    with pytest.raises((QuestionIntegrityError,ValueError,TypeError)): make_question(Registry(),formulation="X?",question_type=QuestionType.EXPLANATORY,context={},constraints={},status="INVALID")
# 09
def test_gate_09_only_registered_evidence(): assert q(evidence=(H1,)).evidence_hashes==(H1,)
# 10
def test_gate_10_unknown_evidence_rejected():
    with pytest.raises(QuestionIntegrityError): make_question(Registry(),formulation="X?",question_type=QuestionType.EXPLANATORY,context={},constraints={},evidence_hashes=(H1,))
# 11
def test_gate_11_evidence_integrity_verified():
    x=Evidence(H1); x.verify_integrity=lambda:False
    with pytest.raises(QuestionIntegrityError): make_question(Registry(x),formulation="X?",question_type=QuestionType.EXPLANATORY,context={},constraints={},evidence_hashes=(H1,))
# 12
def test_gate_12_claim_integrity_verified():
    class Bad(Claim):
        def verify(self,registry): raise QuestionIntegrityError("bad claim")
    c=Bad(C1,(H1,)); r=Registry(Evidence(H1))
    with pytest.raises(QuestionIntegrityError): make_question(r,formulation="X?",question_type=QuestionType.EXPLANATORY,context={},constraints={},evidence_hashes=(H1,),claim_hashes=(C1,),claims=(c,))
# 13
def test_gate_13_evidence_claim_substitution_rejected():
    c=Claim(C1,(H1,)); r=Registry(Evidence(H2))
    with pytest.raises(QuestionIntegrityError): make_question(r,formulation="X?",question_type=QuestionType.EXPLANATORY,context={},constraints={},evidence_hashes=(H2,),claim_hashes=(C1,),claims=(c,))
# 14
def test_gate_14_evidence_tampering_detected():
    x=q(evidence=(H1,)); p=dict(x.export()); p["evidence_hashes"]=(H2,)
    with pytest.raises(QuestionIntegrityError): ResearchQuestion.from_export(p)
# 15
def test_gate_15_complete_provenance_preserved():
    x=q(evidence=(H1,)); assert x.provenance[H1]["result_hash"]==H1 and x.provenance[H1]["trace_hash"]==T1 and x.provenance[H1]["event_ids"]==(H2,)
# 16
def test_gate_16_recursive_provenance_preserved():
    x=q(evidence=(H1,)); assert "state_anchors" in x.export()["provenance"][H1]
# 17
def test_gate_17_unanswered_question_detected():
    x=q(); assert x.status is QuestionStatus.UNRESOLVED and x.resolution["class"]=="UNRESOLVED"
# 18
def test_gate_18_evidence_gap_detected():
    x=q(status=QuestionStatus.GAP,constraints={"required_evidence":(H1,)}); assert x.status is QuestionStatus.GAP and x.resolution["class"]=="GAP"
# 19
def test_gate_19_conflicting_evidence_detected():
    r=Registry(Evidence(H1,"SUPPORTED"),Evidence(H2,"REFUTED")); x=make_question(r,formulation="Is X true?",question_type=QuestionType.COMPARATIVE,context={},constraints={},evidence_hashes=(H1,H2)); assert x.status is QuestionStatus.CONFLICTING
# 20
def test_gate_20_sufficient_evidence_answered(): assert resolve_question(q(evidence=(H1,)),evidence_statuses={H1:"SUPPORTED"}).status is QuestionStatus.ANSWERED
# 21
def test_gate_21_insufficient_evidence_not_answered(): assert resolve_question(q(),evidence_statuses={}).status is not QuestionStatus.ANSWERED
# 22
def test_gate_22_contradictory_claims_cannot_silently_collapse():
    r=Registry(Evidence(H1),Evidence(H2)); c1=Claim(C1,(H1,),"SUPPORTED"); c2=Claim(C2,(H2,),"REFUTED")
    x=make_question(r,formulation="Is X true?",question_type=QuestionType.COMPARATIVE,context={},constraints={},evidence_hashes=(H1,H2),claim_hashes=(C1,C2),claims=(c1,c2)); assert x.status is QuestionStatus.CONFLICTING
# 23
def test_gate_23_deterministic_resolution_classification(): assert q(evidence=(H1,)).resolution==q(evidence=(H1,)).resolution
# 24
def test_gate_24_resolution_explanation_is_provenance_addressed(): assert q(evidence=(H1,)).resolution["explanation_refs"]==(H1,)
# 25
def test_gate_25_hypothesis_references_preserved():
    h=Hypothesis(H1); assert q(hypotheses=(h,)).hypothesis_hashes==(H1,)
# 26
def test_gate_26_question_hypothesis_linkage_integrity():
    h=Hypothesis(H1); x=q(hypotheses=(h,)); assert x.verify(hypotheses=(h,))
    with pytest.raises(QuestionIntegrityError): x.verify(hypotheses=(Hypothesis(H2),))
# 27
def test_gate_27_descendant_question_lineage_preserved():
    p=q(); c=q(parent_question_hash=p.question_hash); assert c.parent_question_hash==p.question_hash and c.lineage==(p.question_hash,c.question_hash)
# 28
def test_gate_28_ancestor_cannot_be_rewritten():
    p=q(formulation="Original question?"); c=q(formulation="Refined question?",parent_question_hash=p.question_hash); assert p.formulation=="Original question?" and c.question_hash!=p.question_hash
# 29
def test_gate_29_cyclic_research_lineage_rejected():
    p=q()
    with pytest.raises(QuestionIntegrityError): q(parent_question_hash=p.question_hash,constraints={"lineage":(p.question_hash,p.question_hash)})
# 30
def test_gate_30_question_payload_tampering_detected():
    p=dict(q().export()); p["formulation"]="Tampered?"
    with pytest.raises(QuestionIntegrityError): ResearchQuestion.from_export(p)
# 31
def test_gate_31_evidence_substitution_attack_rejected():
    x=q(evidence=(H1,))
    with pytest.raises(QuestionIntegrityError): x.verify(evidence=(H2,))
# 32
def test_gate_32_runtime_metadata_injection_rejected():
    for k in ("timestamp","uuid","memory_address","environment","local_path","hostname","pid","process_id"):
        with pytest.raises(QuestionIntegrityError): q(context={k:"forbidden"})
# 33
def test_gate_33_cross_runtime_byte_identical_reproduction():
    kw=dict(formulation=" Why  does X occur? ",question_type=QuestionType.EXPLANATORY,context={"b":[2,1],"a":{"z":3,"x":4}},constraints={"scope":"test"},evidence_hashes=(H1,)); a=compute_question_hash(**kw); b=compute_question_hash(**kw); assert a==b and hashlib.sha256(json.dumps(a,sort_keys=True).encode()).digest()==hashlib.sha256(json.dumps(b,sort_keys=True).encode()).digest()
# 34
def test_gate_34_zero_io_network_domain_contamination():
    import jamp.research.question_engine as m
    source=open(m.__file__,encoding="utf-8").read(); assert "jamp.domain" not in m.__dict__.get("__file__","") and "import socket" not in source and "import requests" not in source and "Path(" not in source
