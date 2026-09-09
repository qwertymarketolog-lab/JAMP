"""Executable P20.10 acceptance/adversarial contract."""
import hashlib
import importlib
import json
import pytest
from dataclasses import FrozenInstanceError

E = lambda: importlib.import_module("jamp.research.consensus")
H = lambda s: hashlib.sha256(s.encode()).hexdigest()

class FakeInterpretation:
    def __init__(self, h, classification="SUPPORTS", result_hash=None, execution_hash=None, plan_hash=None, question_hash=None, trace_hash=None, state_hash=None, target="T", method="M", parameters=None, conclusion="C"):
        self.interpretation_hash=h; self.classification=classification; self.result_hash=result_hash or H("result"+h)
        self.execution_hash=execution_hash or H("exec"+h); self.plan_hash=plan_hash or H("plan"+h); self.question_hash=question_hash or H("question"+h)
        self.trace_hash=trace_hash or H("trace"+h); self.state_hash=state_hash or H("state"+h)
        self.analytical_target=target; self.method=method; self.parameters=parameters or {"p": 1}; self.conclusion=conclusion
    def provenance_chain(self): return (self.question_hash,self.plan_hash,self.execution_hash,self.result_hash,self.trace_hash,self.state_hash)
    def verify(self, registry=None): return True

@pytest.fixture
def data():
    a=FakeInterpretation(H("a"),"SUPPORTS"); b=FakeInterpretation(H("b"),"REFUTES")
    return {a.interpretation_hash:a,b.interpretation_hash:b},a,b

def test_schema_validity(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={"x":1})
    assert c.verify(data[0])

def test_immutable_claim_record(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={})
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)): c.statement="X"

def test_deterministic_claim_hash(data):
    a=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={"x":1})
    b=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={"x":1})
    assert a.claim_hash==b.claim_hash

def test_self_verification(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={})
    assert c.verify(data[0]) is True

def test_interpretation_bindings(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={})
    assert c.interpretation_hashes==(data[1].interpretation_hash,)

def test_target_identification(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={})
    assert c.target=="T"

def test_formulation_method(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="synthesis", parameters={})
    assert c.method=="synthesis"

def test_canonical_parameters(data):
    a=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={"b":2,"a":1})
    b=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={"a":1,"b":2})
    assert a.claim_hash==b.claim_hash

def test_runtime_independence(data):
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={"timestamp":1})

def test_claim_epistemic_boundary(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.status.value!="ABSOLUTE_TRUTH"

def test_interpretation_exists(data):
    assert E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={}).verify(data[0])

def test_unknown_interpretation_rejected(data):
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim(data[0], statement="T", interpretations=[FakeInterpretation(H("unknown"))], method="s", parameters={})

def test_upstream_execution_preserved(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.execution_hashes==(data[1].execution_hash,)

def test_upstream_plan_preserved(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.plan_hashes==(data[1].plan_hash,)

def test_upstream_question_preserved(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.question_hashes==(data[1].question_hash,)

def test_trace_state_anchors_preserved(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.trace_hashes==(data[1].trace_hash,) and c.state_hashes==(data[1].state_hash,)

def test_recursive_provenance_verified(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.provenance_chain()==data[1].provenance_chain()

def test_interpretation_substitution_rejected(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    with pytest.raises(E().ConsensusIntegrityError): c.verify({data[2].interpretation_hash:data[2]})

def test_support_conflict_mapping(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1],data[2]], method="s", parameters={})
    assert c.supporting_hashes==(data[1].interpretation_hash,) and c.conflicting_hashes==(data[2].interpretation_hash,)

def test_structured_consensus_state(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.consensus.status.value=="CONSENSUS"

def test_persistent_controversy_preserved(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1],data[2]], method="s", parameters={})
    assert c.consensus.status.value=="CONTESTED" and len(c.consensus.dissenting_hashes)==1

def test_false_consensus_blocked(data):
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim(data[0], statement="T", interpretations=[data[1],data[2]], method="s", parameters={}, consensus_status="CONSENSUS")

def test_unbacked_claim_blocked(data):
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim({}, statement="T", interpretations=[data[1]], method="s", parameters={})

def test_unsupported_claim_blocked(data):
    u=FakeInterpretation(H("u"),"UNDETERMINED")
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim({u.interpretation_hash:u}, statement="T", interpretations=[u], method="s", parameters={}, consensus_status="CONSENSUS")

def test_consensus_requires_evidence(data):
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim({}, statement="T", interpretations=[], method="s", parameters={})

def test_dissent_never_erased(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1],data[2]], method="s", parameters={})
    assert set(c.consensus.dissenting_hashes)=={data[2].interpretation_hash}

def test_claim_resolution_is_falsifiable(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.falsifiable is True

def test_claim_never_becomes_absolute_truth(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.epistemic_status.value!="ABSOLUTE"

def test_canonical_composition(data):
    a=E().make_claim(data[0], statement="T", interpretations=[data[1],data[2]], method="s", parameters={})
    b=E().make_claim(data[0], statement="T", interpretations=[data[2],data[1]], method="s", parameters={})
    assert a.claim_hash==b.claim_hash

def test_deterministic_claim_hash_reproduction(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert E().compute_claim_hash(c.canonical_payload())==c.claim_hash

def test_equivalent_claims_same_hash(data):
    x=E().make_claim(data[0], statement=" T ", interpretations=[data[1]], method="s", parameters={})
    y=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert x.claim_hash==y.claim_hash

def test_material_change_distinct_hash(data):
    x=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    y=E().make_claim(data[0], statement="U", interpretations=[data[1]], method="s", parameters={})
    assert x.claim_hash!=y.claim_hash

def test_content_addressed_provenance(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    assert c.consensus.consensus_hash==E().compute_consensus_hash(c.consensus.canonical_payload())

def test_deterministic_resolution(data):
    a=E().make_claim(data[0], statement="T", interpretations=[data[1],data[2]], method="s", parameters={})
    b=E().make_claim(data[0], statement="T", interpretations=[data[2],data[1]], method="s", parameters={})
    assert a.consensus.status==b.consensus.status and a.consensus.consensus_hash==b.consensus.consensus_hash

def test_payload_tampering_detected(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    object.__setattr__(c,"statement","tampered")
    with pytest.raises(E().ConsensusIntegrityError): c.verify(data[0])

def test_interpretation_substitution_attack_blocked(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={})
    altered=FakeInterpretation(H("altered"),"SUPPORTS", result_hash=data[1].result_hash)
    with pytest.raises(E().ConsensusIntegrityError): c.verify({altered.interpretation_hash:altered})

def test_runtime_metadata_injection_blocked(data):
    with pytest.raises(E().ConsensusIntegrityError): E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={"uuid":"x"})

def test_cross_runtime_byte_identity(data):
    c=E().make_claim(data[0], statement="T", interpretations=[data[1]], method="s", parameters={"x":1})
    assert json.dumps(c.export(),sort_keys=True,separators=(",",":"))==json.dumps(E().make_claim(data[0],statement="T",interpretations=[data[1]],method="s",parameters={"x":1}).export(),sort_keys=True,separators=(",",":"))

def test_zero_io_network_contamination():
    src=E().__file__ if hasattr(E(),"__file__") else importlib.import_module("jamp.research.consensus").__file__
    text=open(src,encoding="utf-8").read()
    assert "socket" not in text and "requests" not in text and "urllib" not in text

def test_zero_domain_contamination():
    mod=importlib.import_module("jamp.research.consensus")
    assert not any((getattr(x,"__module__","").startswith("jamp.domain")) for x in vars(mod).values())
