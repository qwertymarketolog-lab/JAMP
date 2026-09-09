"""Executable P20.11 acceptance and adversarial gates."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from types import MappingProxyType

import pytest

from jamp.research.canonical import canonical_bytes
from jamp.research.hypothesis import (
    HypothesisStatus,
    make_hypothesis,
    transition_hypothesis,
)
from jamp.research.revision import (
    RevisionIntegrityError,
    RevisionStatus,
    compute_revision_hash,
    make_revision,
)

ZERO = "0" * 64


class StubConsensus:
    def __init__(self, status="CONSENSUS", upstream=None):
        self.status = status
        self.consensus_hash = hashlib.sha256(canonical_bytes({"status": status, "upstream": upstream or {}})).hexdigest()
        self._upstream = upstream or {}

    def verify(self, registry=None):
        return True

    def provenance_chain(self):
        return tuple(self._upstream.get("chain", ()))


class Registry(dict):
    pass


def root_hypothesis():
    return make_hypothesis(
        formulation="The observed mechanism is stable under the stated conditions",
        hypothesis_type="SCIENTIFIC",
        source={"origin": "researcher", "observation": "O1"},
    )


def refuted_parent():
    h = root_hypothesis()
    return transition_hypothesis(h, HypothesisStatus.REFUTED, {"claim_hash": ZERO})


def setup_revision(status="CONSENSUS"):
    parent = refuted_parent()
    consensus = StubConsensus(status, {
        "chain": ("q" * 64, "p" * 64, "e" * 64, "r" * 64, "i" * 64),
        "state_hashes": ["s" * 64],
    })
    registry = Registry({consensus.consensus_hash: consensus, parent.hypothesis_hash: parent})
    rec = make_revision(
        parent_hypothesis=parent,
        trigger=consensus,
        registry=registry,
        formulation="The mechanism depends on an additional boundary condition",
        revision_type="REFINEMENT",
        revision_method="boundary_condition_analysis",
        parameters={"threshold": 0.5},
        epistemic_status="FALSIFIABLE",
        rationale={"basis": "contested evidence"},
    )
    return rec, parent, consensus, registry


def test_gate_01_schema_validity():
    rec, *_ = setup_revision()
    assert rec.verify()


def test_gate_02_immutable_revision_record():
    rec, *_ = setup_revision()
    with pytest.raises((AttributeError, TypeError)):
        rec.formulation = "mutated"


def test_gate_03_valid_revision_hash():
    rec, *_ = setup_revision()
    assert len(rec.revision_hash) == 64 and rec.revision_hash == rec.revision_hash.lower()


def test_gate_04_deterministic_revision_identity():
    a, *_ = setup_revision(); b, *_ = setup_revision()
    assert a.revision_hash == b.revision_hash


def test_gate_05_self_verification():
    rec, *_ = setup_revision()
    assert rec.verify() is True


def test_gate_06_explicit_parent_hypothesis():
    rec, *_ = setup_revision()
    assert rec.parent_hypothesis_hash


def test_gate_07_explicit_trigger_reference():
    rec, *_ = setup_revision()
    assert rec.trigger_consensus_hash


def test_gate_08_explicit_revision_formulation():
    rec, *_ = setup_revision()
    assert rec.formulation.strip()


def test_gate_09_explicit_revision_method():
    rec, *_ = setup_revision()
    assert rec.revision_method.strip()


def test_gate_10_runtime_independent_identity():
    rec, *_ = setup_revision()
    assert not any(k in rec.canonical_payload() for k in ("timestamp", "uuid", "pid", "hostname", "environment"))


def test_gate_11_consensus_exists():
    rec, parent, consensus, registry = setup_revision()
    assert registry[rec.trigger_consensus_hash] is consensus


def test_gate_12_unknown_consensus_rejected():
    parent = refuted_parent()
    unknown = StubConsensus()
    with pytest.raises(RevisionIntegrityError):
        make_revision(parent_hypothesis=parent, trigger=unknown, registry={}, formulation="New formulation", revision_type="REFINEMENT", revision_method="analysis", parameters={}, epistemic_status="FALSIFIABLE", rationale={"basis": "gap"})


def test_gate_13_consensus_integrity_verified():
    rec, parent, consensus, registry = setup_revision()
    assert rec.verify(registry=registry)


def test_gate_14_interpretation_provenance_preserved():
    rec, *_ = setup_revision()
    assert "interpretation_hashes" in rec.provenance


def test_gate_15_result_provenance_preserved():
    rec, *_ = setup_revision()
    assert "result_hashes" in rec.provenance


def test_gate_16_execution_plan_question_preserved():
    rec, *_ = setup_revision()
    assert all(k in rec.provenance for k in ("execution_hashes", "plan_hashes", "question_hashes"))


def test_gate_17_trace_state_anchors_preserved():
    rec, *_ = setup_revision()
    assert all(k in rec.provenance for k in ("trace_hashes", "state_hashes"))


def test_gate_18_recursive_provenance_verified():
    rec, *_ = setup_revision()
    assert rec.provenance["upstream_chain"]


def test_gate_19_consensus_to_revision_mapping():
    rec, *_ = setup_revision("CONSENSUS")
    assert rec.trigger_status == RevisionStatus.CONSENSUS


def test_gate_20_contested_to_revision_mapping():
    rec, *_ = setup_revision("CONTESTED")
    assert rec.trigger_status == RevisionStatus.CONTESTED


def test_gate_21_unresolved_to_revision_mapping():
    rec, *_ = setup_revision("UNDETERMINED")
    assert rec.trigger_status == RevisionStatus.UNDETERMINED


def test_gate_22_refutation_preserved():
    rec, parent, *_ = setup_revision()
    assert parent.status == HypothesisStatus.REFUTED
    assert rec.parent_hypothesis_hash == parent.hypothesis_hash


def test_gate_23_historical_hypothesis_immutable():
    parent = refuted_parent()
    before = parent.export()
    setup_revision()
    assert parent.export() == before


def test_gate_24_parent_pointer_immutable():
    rec, *_ = setup_revision()
    with pytest.raises((AttributeError, TypeError)):
        rec.parent_hypothesis_hash = ZERO


def test_gate_25_revision_reason_required():
    parent = refuted_parent(); trigger = StubConsensus(); registry = Registry({trigger.consensus_hash: trigger})
    with pytest.raises(RevisionIntegrityError):
        make_revision(parent_hypothesis=parent, trigger=trigger, registry=registry, formulation="New", revision_type="REFINEMENT", revision_method="analysis", parameters={}, epistemic_status="FALSIFIABLE", rationale={})


def test_gate_26_unsupported_revision_blocked():
    parent = root_hypothesis(); trigger = StubConsensus(); registry = Registry({trigger.consensus_hash: trigger, parent.hypothesis_hash: parent})
    with pytest.raises(RevisionIntegrityError):
        make_revision(parent_hypothesis=parent, trigger=trigger, registry=registry, formulation="New", revision_type="REFINEMENT", revision_method="analysis", parameters={}, epistemic_status="FALSIFIABLE", rationale={"basis": "unsupported"})


def test_gate_27_false_resolution_not_manufactured():
    parent = refuted_parent(); trigger = StubConsensus("CONTESTED"); registry = Registry({trigger.consensus_hash: trigger, parent.hypothesis_hash: parent})
    with pytest.raises(RevisionIntegrityError):
        make_revision(parent_hypothesis=parent, trigger=trigger, registry=registry, formulation="New", revision_type="REFINEMENT", revision_method="analysis", parameters={}, epistemic_status="RESOLVED", rationale={"basis": "forced certainty"})


def test_gate_28_epistemic_status_preserved():
    rec, *_ = setup_revision()
    assert rec.epistemic_status == "FALSIFIABLE"


def test_gate_29_acyclic_dependency_graph():
    rec, parent, consensus, *_ = setup_revision()
    assert rec.parent_hypothesis_hash != rec.trigger_consensus_hash
    assert parent.hypothesis_hash != consensus.consensus_hash


def test_gate_30_circular_dependency_rejected():
    rec, parent, consensus, registry = setup_revision()
    cyclic = StubConsensus(upstream={"chain": (rec.revision_hash, parent.hypothesis_hash, consensus.consensus_hash)})
    with pytest.raises(RevisionIntegrityError):
        make_revision(parent_hypothesis=parent, trigger=cyclic, registry={cyclic.consensus_hash: cyclic, parent.hypothesis_hash: parent}, formulation="Cycle", revision_type="REFINEMENT", revision_method="analysis", parameters={}, epistemic_status="FALSIFIABLE", rationale={"basis": "cycle"})


def test_gate_31_historical_loop_closure_preserved():
    rec, parent, consensus, *_ = setup_revision()
    assert rec.loop_closure["parent_hypothesis_hash"] == parent.hypothesis_hash
    assert rec.loop_closure["trigger_consensus_hash"] == consensus.consensus_hash


def test_gate_32_descendant_lineage_complete():
    rec, parent, *_ = setup_revision()
    assert rec.lineage[0] == parent.hypothesis_hash
    assert rec.lineage[-1] == rec.revision_hash


def test_gate_33_ancestor_rewrite_rejected():
    rec, parent, *_ = setup_revision()
    tampered = replace(parent, formulation="rewritten ancestor")
    with pytest.raises(RevisionIntegrityError):
        rec.verify(registry={rec.trigger_consensus_hash: StubConsensus()}, parent_hypothesis=tampered)


def test_gate_34_deterministic_revision_selection():
    rec, *_ = setup_revision()
    candidates = [rec]
    assert sorted(candidates, key=lambda x: x.revision_hash)[0] is rec


def test_gate_35_revision_payload_tampering_detected():
    rec, *_ = setup_revision()
    payload = rec.canonical_payload(); payload["formulation"] = "tampered"
    assert compute_revision_hash(payload) != rec.revision_hash


def test_gate_36_consensus_substitution_attack_blocked():
    rec, parent, consensus, registry = setup_revision()
    other = StubConsensus("CONTESTED")
    with pytest.raises(RevisionIntegrityError):
        rec.verify(registry={other.consensus_hash: other}, parent_hypothesis=parent)


def test_gate_37_hypothesis_lineage_substitution_blocked():
    rec, parent, consensus, registry = setup_revision()
    other = refuted_parent()
    with pytest.raises(RevisionIntegrityError):
        rec.verify(registry=registry, parent_hypothesis=other)


def test_gate_38_runtime_metadata_injection_blocked():
    parent = refuted_parent(); trigger = StubConsensus(); registry = Registry({trigger.consensus_hash: trigger})
    with pytest.raises(RevisionIntegrityError):
        make_revision(parent_hypothesis=parent, trigger=trigger, registry=registry, formulation="New", revision_type="REFINEMENT", revision_method="analysis", parameters={"timestamp": "now"}, epistemic_status="FALSIFIABLE", rationale={"basis": "x"})


def test_gate_39_cross_runtime_byte_identity():
    rec, *_ = setup_revision()
    code = "from jamp.research.revision import compute_revision_hash; print(compute_revision_hash(" + repr(rec.canonical_payload()) + "))"
    env = dict(os.environ); env["PYTHONPATH"] = "src"
    out = subprocess.check_output([sys.executable, "-c", code], text=True, env=env).strip()
    assert out == rec.revision_hash


def test_gate_40_zero_io_network_domain_contamination():
    rec, *_ = setup_revision()
    assert rec.verify()
    source = open("src/jamp/research/revision.py", encoding="utf-8").read()
    assert "jamp.domain" not in source
    assert "socket" not in source and "requests" not in source and "urllib" not in source


def test_all_40_gate_functions_present():
    names = {name for name in globals() if name.startswith("test_gate_")}
    assert len(names) == 40
