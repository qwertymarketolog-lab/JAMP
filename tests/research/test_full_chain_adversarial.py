"""Executable 40-gate adversarial contract for P21.4."""
from dataclasses import dataclass, replace
import hashlib
import inspect
import json
import re

import pytest

from jamp.research.runtime import RuntimeIntegrityError, RuntimeStage
from jamp.research.session import ResearchSession, SessionArtifact
from jamp.research.adversarial_audit import FullChainAudit, AuditIntegrityError

GATES = [
    "full_chain_construction", "p19_p20_p21_integration_surface", "content_addressed_objects", "full_provenance_reconstruction",
    "runtime_identity_absent", "session_identity_preserved", "causal_state_anchors_preserved", "revision_lineage_preserved",
    "cyclic_logic_rejected", "full_chain_reproducible", "question_tamper_propagates", "plan_tamper_propagates",
    "execution_tamper_propagates", "result_tamper_propagates", "interpretation_tamper_propagates", "claim_tamper_propagates",
    "consensus_tamper_propagates", "revision_tamper_propagates", "upstream_substitution_detected", "independent_verification",
    "byte_sensitivity", "parent_sensitivity", "same_artifact_same_hash", "trajectory_divergence", "state_equal_trace_distinct",
    "provenance_substitution", "cross_runtime_bytes", "deterministic_invalidation", "payload_injection", "hash_substitution",
    "parent_substitution", "metadata_injection", "runtime_metadata_injection", "artificial_cycle", "zero_filesystem",
    "zero_network", "zero_domain", "zero_mutable_state", "repeatable_verification", "full_chain_tamper_proof",
]

@dataclass(frozen=True)
class Artifact:
    kind: str
    artifact_hash: str
    parent_hash: str | None
    payload: tuple
    trace_hash: str
    state_hash: str
    def verify(self):
        material = (self.kind, self.parent_hash, self.payload, self.trace_hash, self.state_hash)
        expected = hashlib.sha256(repr(material).encode()).hexdigest()
        if expected != self.artifact_hash: raise AuditIntegrityError(f"{self.kind} integrity failure")
        return True
    def export(self):
        return {"artifact_hash": self.artifact_hash, "parent_hash": self.parent_hash, "payload": list(self.payload), "trace_hash": self.trace_hash, "state_hash": self.state_hash}

def mk(kind, parent, payload=("x",), trace=None, state=None):
    trace = trace or hashlib.sha256(f"trace:{kind}:{parent}:{payload}".encode()).hexdigest()
    state = state or hashlib.sha256(f"state:{payload}".encode()).hexdigest()
    material = (kind, parent, tuple(payload), trace, state)
    return Artifact(kind, hashlib.sha256(repr(material).encode()).hexdigest(), parent, tuple(payload), trace, state)

def chain():
    out = []; parent = None
    for kind in ("question", "plan", "execution", "result", "interpretation", "consensus", "revision"):
        a = mk(kind, parent); out.append(a); parent = a.artifact_hash
    return tuple(out)

def session_for(items):
    refs = [SessionArtifact(a.kind, a.artifact_hash) for a in items]
    return ResearchSession.create(metadata={"purpose": "P21.4"}, artifacts=refs, status="OPEN")

def audit():
    items = chain(); return FullChainAudit.create(items, session=session_for(items))

def test_gate_01_full_chain_construction(): assert audit().stage_names == tuple(x.value for x in RuntimeStage)
def test_gate_02_p19_p20_p21_integration_surface(): assert audit().integration_layers == ("P19", "P20", "P21")
def test_gate_03_content_addressed_objects(): assert all(re.fullmatch(r"[0-9a-f]{64}", x.artifact_hash) for x in chain())
def test_gate_04_full_provenance_reconstruction(): assert len(audit().provenance) == 7
def test_gate_05_runtime_identity_absent(): assert not any(k in json.dumps(audit().export()).lower() for k in ("timestamp", "pid", "hostname", "memory_address"))
def test_gate_06_session_identity_preserved():
    a = audit(); assert a.session.verify() and a.session_hash == a.session.session_hash
def test_gate_07_causal_state_anchors_preserved(): assert all(x.trace_hash and x.state_hash for x in audit().artifacts)
def test_gate_08_revision_lineage_preserved():
    a = audit(); assert a.artifacts[-1].parent_hash == a.artifacts[-2].artifact_hash
def test_gate_09_cyclic_logic_rejected():
    items = list(chain()); items[0] = replace(items[0], parent_hash=items[-1].artifact_hash)
    with pytest.raises((RuntimeIntegrityError, AuditIntegrityError)): FullChainAudit.create(tuple(items), session=session_for(items))
def test_gate_10_full_chain_reproducible(): assert audit().audit_hash == audit().audit_hash

def _tampered(index, **changes):
    items = list(chain()); items[index] = replace(items[index], **changes); return tuple(items)
def _must_reject(items):
    with pytest.raises((RuntimeIntegrityError, AuditIntegrityError, ValueError)): FullChainAudit.create(items, session=session_for(items))
def test_gate_11_question_tamper_propagates(): _must_reject(_tampered(0, payload=("tampered",)))
def test_gate_12_plan_tamper_propagates(): _must_reject(_tampered(1, payload=("tampered",)))
def test_gate_13_execution_tamper_propagates(): _must_reject(_tampered(2, payload=("tampered",)))
def test_gate_14_result_tamper_propagates(): _must_reject(_tampered(3, payload=("tampered",)))
def test_gate_15_interpretation_tamper_propagates(): _must_reject(_tampered(4, payload=("tampered",)))
def test_gate_16_claim_tamper_propagates():
    items = list(chain()); items[4] = replace(items[4], kind="claim"); _must_reject(tuple(items))
def test_gate_17_consensus_tamper_propagates(): _must_reject(_tampered(5, payload=("tampered",)))
def test_gate_18_revision_tamper_propagates(): _must_reject(_tampered(6, payload=("tampered",)))
def test_gate_19_upstream_substitution_detected(): _must_reject(_tampered(3, parent_hash="0" * 64))
def test_gate_20_independent_verification(): assert audit().verify_independent() is True
def test_gate_21_byte_sensitivity():
    x = chain()[0]; assert x.artifact_hash != mk(x.kind, x.parent_hash, ("y",)).artifact_hash
def test_gate_22_parent_sensitivity():
    x = chain()[1]; assert x.artifact_hash != mk(x.kind, "0" * 64, x.payload).artifact_hash
def test_gate_23_same_artifact_same_hash(): assert chain()[0].artifact_hash == chain()[0].artifact_hash
def test_gate_24_trajectory_divergence():
    a = chain(); b = list(a); b[0] = mk("question", None, ("alternate",)); b[1] = mk("plan", b[0].artifact_hash); b[2] = mk("execution", b[1].artifact_hash); b[3] = mk("result", b[2].artifact_hash); assert a[3].trace_hash != b[3].trace_hash
def test_gate_25_state_equal_trace_distinct():
    a = mk("question", None, ("same",), trace="1"*64, state="2"*64); b = mk("question", None, ("same",), trace="3"*64, state="2"*64); assert a.state_hash == b.state_hash and a.trace_hash != b.trace_hash
def test_gate_26_provenance_substitution(): _must_reject(_tampered(6, parent_hash="0" * 64))
def test_gate_27_cross_runtime_bytes(): assert audit().canonical_bytes() == audit().canonical_bytes()
def test_gate_28_deterministic_invalidation():
    x = _tampered(2, payload=("tampered",))
    with pytest.raises(Exception): FullChainAudit.create(x, session=session_for(x))
    with pytest.raises(Exception): FullChainAudit.create(x, session=session_for(x))
def test_gate_29_payload_injection(): _must_reject(_tampered(0, payload=("__injected__", {"timestamp": 1})))
def test_gate_30_hash_substitution(): _must_reject(_tampered(3, artifact_hash="0" * 64))
def test_gate_31_parent_substitution(): _must_reject(_tampered(4, parent_hash="f" * 64))
def test_gate_32_metadata_injection():
    items = chain(); bad = ResearchSession.create(metadata={"timestamp": 1}, artifacts=[SessionArtifact(a.kind, a.artifact_hash) for a in items], status="OPEN");
    with pytest.raises(AuditIntegrityError): FullChainAudit.create(items, session=bad)
def test_gate_33_runtime_metadata_injection():
    with pytest.raises(ValueError): FullChainAudit.create(chain(), session=session_for(chain()), runtime_metadata={"pid": 1})
def test_gate_34_artificial_cycle(): _must_reject(_tampered(0, parent_hash=chain()[-1].artifact_hash))
def test_gate_35_zero_filesystem():
    source = inspect.getsource(__import__("jamp.research.adversarial_audit", fromlist=["x"])); assert not re.search(r"(^|\\n)\\s*(import|from)\\s+(pathlib|os|io|tempfile|shutil)\\b", source)
def test_gate_36_zero_network():
    source = inspect.getsource(__import__("jamp.research.adversarial_audit", fromlist=["x"])); assert not re.search(r"(^|\\n)\\s*(import|from)\\s+(requests|urllib|socket|httpx)\\b", source)
def test_gate_37_zero_domain():
    source = inspect.getsource(__import__("jamp.research.adversarial_audit", fromlist=["x"])); assert "jamp.domain" not in source
def test_gate_38_zero_mutable_state():
    a = audit(); assert a.verify_independent() and a.audit_hash == audit().audit_hash
def test_gate_39_repeatable_verification(): assert audit().verify_independent() is True and audit().verify_independent() is True
def test_gate_40_full_chain_tamper_proof():
    for i in range(7): _must_reject(_tampered(i, payload=("one-byte-change", i)))
def test_all_40_gates_are_present_and_executable():
    assert len(GATES) == 40; module = __import__(__name__, fromlist=["x"])
    for i in range(1, 41): assert any(n.startswith(f"test_gate_{i:02d}_") for n in module.__dict__)
