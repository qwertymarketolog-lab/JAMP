import hashlib,json
from pathlib import Path
import pytest
from src.jamp.runtime import CapabilityResolver,EvidenceGate,ModelSelector,ProvenanceTracker,TaskClassifier
CORE="0fee0e1c5c1a1548361965ac51eacdeba62bfe8a";AID=11369355096;SHA="7785cbd5ae19704473b385b8b21ddbdf7cd9eeb06aee56ce0f66e7da7592f1f1"
def blob_sha(b):return hashlib.sha1(f"blob {len(b)}\\0".encode()+b).hexdigest()
def fixture():return json.loads((Path(__file__).parent/"fixtures/runtime_evidence_projection.json").read_text())
def test_frozen_core_blob_is_exact():assert blob_sha(Path("src/jamp/run.py").read_bytes())==CORE
def test_source_identity():
 d=fixture();assert d["source"]["artifact_id"]==AID and d["source"]["sha256"]==SHA and d["frozen_core_blob"]==CORE and len(d["models"])==17
def test_counts_and_refusal():
 d=fixture();g=EvidenceGate({"contract_version":"jamp-17-capability-v1","canonical_manifest_sha256":d["source"]["manifest_sha256"],"frozen_core_blob":CORE,"expected_models":17,"executed_models":17,"expected_checks":170,"executed_checks":170,"models":d["models"]});r,s=CapabilityResolver(),ModelSelector();exp={"search_and_extraction":12,"tool_execution_agent":7,"long_context_analysis":0,"strict_compliance_safety":2}
 for task,n in exp.items():
  e=g.get_eligible_models(r.get_required_capabilities(task));assert len(e)==n;a,m=s.select_model(e,task);assert a==("REFUSE" if n==0 else "EXECUTE");assert m=="ZERO_ELIGIBLE_MODELS" if n==0 else True
def test_classifier_fail_closed():
 c=TaskClassifier();assert c.classify({"classification_entropy":.86})=="strict_compliance_safety";assert c.classify({"token_count":16001})=="long_context_analysis"
 with pytest.raises(ValueError):c.classify({"intent":"unknown"})
def test_refusal_provenance():
 t=ProvenanceTracker().create_trace("long_context_analysis",["C03","C08"],"REFUSE","ZERO_ELIGIBLE_MODELS",0);assert t["status"]=="REFUSE";assert t["frozen_core_state"]=={"blob":CORE,"delta":0};assert t["gate_evaluator"]["evidence_base_sha256"]==SHA;assert "refusal_details" in t
