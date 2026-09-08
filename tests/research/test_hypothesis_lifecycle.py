"""P20.5 executable acceptance and adversarial tests.

Every frozen gate is exercised by behavior, not by a declarative name check.
The suite intentionally attacks immutability, provenance, FSM legality,
lineage, tamper detection, determinism, and isolation boundaries.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from jamp.research.canonical import canonical_bytes
from jamp.research.claim import Claim, ClaimStatus, compute_claim_hash
from jamp.research.hypothesis import (
    HypothesisIntegrityError,
    HypothesisStatus,
    HypothesisTransitionError,
    HypothesisRecord,
    compute_hypothesis_hash,
    make_hypothesis,
    transition_hypothesis,
)
from jamp.research.registry import ArtifactRegistry
from jamp.research.replay import ReplayTrace, compute_trace_hash
from jamp.research.result import ResearchResult, compute_result_hash


VALID_HASH = "a" * 64
VALID_HASH_2 = "b" * 64


def _trace(initial: str = "1" * 64, events=("e1",), resulting: str = "2" * 64) -> ReplayTrace:
    trace_hash = compute_trace_hash(initial, events, resulting)
    return ReplayTrace(initial, tuple(events), resulting, trace_hash)


def _result(payload=None) -> ResearchResult:
    trace = _trace()
    payload = {"value": 1} if payload is None else payload
    provenance = {"source": "test", "operation": "measurement", "version": "1"}
    result_hash = compute_result_hash(trace.trace_hash, "measurement", payload, provenance)
    return ResearchResult(trace.trace_hash, "measurement", payload, provenance, result_hash)


def _registry_with_result():
    registry = ArtifactRegistry()
    result = _result()
    registry.register(result, _trace())
    return registry, result


def _claim_without_evidence(status: ClaimStatus = ClaimStatus.UNDETERMINED) -> Claim:
    claim_type = "HYPOTHESIS"
    statement = "A deterministic statement"
    premises = ()
    refs = ()
    rule = "EVIDENCE_STATUS"
    version = "1"
    claim_hash = compute_claim_hash(claim_type, statement, premises, refs, rule, version, status)
    return Claim(claim_type, statement, premises, refs, rule, version, status, {"evidence": {}}, claim_hash)


def _hypothesis(**kwargs):
    defaults = {
        "formulation": "  The system is deterministic. ",
        "hypothesis_type": "SCIENTIFIC",
        "source": {"observation": "repeatable output"},
    }
    defaults.update(kwargs)
    return make_hypothesis(**defaults)


# 01

def test_01_schema_validity():
    h = _hypothesis()
    assert h.verify() is True
    assert h.hypothesis_id == h.hypothesis_hash


# 02

def test_02_immutable_hypothesis_record():
    h = _hypothesis()
    with pytest.raises((FrozenInstanceError, AttributeError)):
        h.status = HypothesisStatus.REFUTED
    with pytest.raises(TypeError):
        h.source["new"] = "value"


# 03

def test_03_valid_hypothesis_hash():
    h = _hypothesis()
    expected = compute_hypothesis_hash(
        h.formulation, h.hypothesis_type, h.source, h.parent_hypothesis_hash,
        h.claim_hashes, h.evidence_hashes, h.status, h.transition_history,
    )
    assert expected == h.hypothesis_hash


# 04

def test_04_deterministic_hash_computation():
    a = _hypothesis(source={"b": 2, "a": [1, 2]})
    b = _hypothesis(source={"a": [1, 2], "b": 2})
    assert a.hypothesis_hash == b.hypothesis_hash


# 05

def test_05_self_verification():
    h = _hypothesis()
    assert h.verify()
    bad = object.__new__(HypothesisRecord)
    object.__setattr__(bad, "formulation", h.formulation)
    object.__setattr__(bad, "hypothesis_type", h.hypothesis_type)
    object.__setattr__(bad, "source", h.source)
    object.__setattr__(bad, "parent_hypothesis_hash", h.parent_hypothesis_hash)
    object.__setattr__(bad, "claim_hashes", h.claim_hashes)
    object.__setattr__(bad, "evidence_hashes", h.evidence_hashes)
    object.__setattr__(bad, "status", h.status)
    object.__setattr__(bad, "transition_history", h.transition_history)
    object.__setattr__(bad, "hypothesis_hash", VALID_HASH)
    with pytest.raises(HypothesisIntegrityError):
        bad.verify()


# 06

def test_06_canonical_formulation():
    h = _hypothesis(formulation="  The   system\n is   deterministic.  ")
    assert h.formulation == "The system is deterministic."


# 07

def test_07_explicit_hypothesis_type():
    with pytest.raises(HypothesisIntegrityError):
        _hypothesis(hypothesis_type="")
    with pytest.raises(HypothesisIntegrityError):
        _hypothesis(hypothesis_type="UNKNOWN")


# 08

def test_08_valid_status():
    h = _hypothesis()
    assert h.status is HypothesisStatus.ACTIVE
    with pytest.raises(HypothesisIntegrityError):
        HypothesisRecord(
            h.formulation, h.hypothesis_type, h.source, None, (), (), "INVALID", (), h.hypothesis_hash
        )


# 09

def test_09_runtime_independent_identity():
    base = _hypothesis(source={"observation": "repeatable output"})
    for key in ("timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"):
        with pytest.raises(HypothesisIntegrityError):
            _hypothesis(source={"observation": "repeatable output", key: "runtime"})
    assert isinstance(base.hypothesis_hash, str) and len(base.hypothesis_hash) == 64


# 10

def test_10_deterministic_export_import():
    h = _hypothesis()
    exported = dict(h.export())
    restored = HypothesisRecord(
        exported["formulation"], exported["hypothesis_type"], exported["source"],
        exported["parent_hypothesis_hash"], tuple(exported["claim_hashes"]),
        tuple(exported["evidence_hashes"]), exported["status"],
        tuple(exported["transition_history"]), exported["hypothesis_hash"],
    )
    assert canonical_bytes(h.export()) == canonical_bytes(restored.export())


# 11

def test_11_registered_evidence_only():
    registry, result = _registry_with_result()
    h = _hypothesis(evidence_hashes=(result.result_hash,))
    assert h.verify(registry=registry)
    unregistered = _hypothesis(evidence_hashes=(VALID_HASH,))
    with pytest.raises(HypothesisIntegrityError):
        unregistered.verify(registry=registry)


# 12

def test_12_unknown_evidence_rejected():
    registry = ArtifactRegistry()
    h = _hypothesis(evidence_hashes=(VALID_HASH,))
    with pytest.raises(HypothesisIntegrityError):
        h.verify(registry=registry)


# 13

def test_13_evidence_integrity_verified():
    registry, result = _registry_with_result()
    h = _hypothesis(evidence_hashes=(result.result_hash,))
    assert h.verify(registry=registry)


# 14

def test_14_claim_integrity_verified():
    registry = ArtifactRegistry()
    claim = _claim_without_evidence()
    h = _hypothesis(claim_hashes=(claim.claim_hash,))
    assert h.verify(registry=registry, claims=(claim,))


# 15

def test_15_claim_evidence_substitution_rejected():
    registry = ArtifactRegistry()
    claim = _claim_without_evidence()
    other = _claim_without_evidence(ClaimStatus.SUPPORTED)
    h = _hypothesis(claim_hashes=(claim.claim_hash,))
    with pytest.raises(HypothesisIntegrityError):
        h.verify(registry=registry, claims=(other,))


# 16

def test_16_evidence_tampering_detected():
    registry, result = _registry_with_result()
    h = _hypothesis(evidence_hashes=(result.result_hash,))
    assert h.verify(registry=registry)
    registry._index[result.result_hash] = MappingProxyType({"trace_hash": VALID_HASH_2})
    with pytest.raises(HypothesisIntegrityError):
        h.verify(registry=registry)


# 17

def test_17_complete_provenance_preserved():
    parent = transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {"claim": VALID_HASH})
    child = _hypothesis(parent=parent, claim_hashes=(VALID_HASH,), evidence_hashes=(VALID_HASH_2,))
    exported = child.export()
    assert exported["parent_hypothesis_hash"] == parent.hypothesis_hash
    assert exported["claim_hashes"] == (VALID_HASH,)
    assert exported["evidence_hashes"] == (VALID_HASH_2,)
    assert len(exported["transition_history"]) == 0
    assert parent.export()["transition_history"][0]["transition_hash"] == parent.transition_history[0]["transition_hash"]


# 18

def test_18_active_to_supported():
    h = transition_hypothesis(_hypothesis(), HypothesisStatus.SUPPORTED, {"claim": VALID_HASH})
    assert h.status is HypothesisStatus.SUPPORTED
    assert h.transition_history[-1]["from_status"] == "ACTIVE"


# 19

def test_19_active_to_refuted():
    h = transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {"claim": VALID_HASH})
    assert h.status is HypothesisStatus.REFUTED
    assert h.is_terminal


# 20

def test_20_active_to_revised():
    h = transition_hypothesis(_hypothesis(), HypothesisStatus.REVISED, {"claim": VALID_HASH})
    assert h.status is HypothesisStatus.REVISED
    child = _hypothesis(parent=h)
    assert child.parent_hypothesis_hash == h.hypothesis_hash


# 21

def test_21_active_to_retired():
    h = transition_hypothesis(_hypothesis(), HypothesisStatus.RETIRED, {"reason": "obsolete"})
    assert h.status is HypothesisStatus.RETIRED
    assert h.is_terminal


# 22

def test_22_supported_transitions():
    supported = transition_hypothesis(_hypothesis(), HypothesisStatus.SUPPORTED, {"claim": VALID_HASH})
    for target in (HypothesisStatus.REFUTED, HypothesisStatus.REVISED, HypothesisStatus.RETIRED):
        result = transition_hypothesis(supported, target, {"claim": VALID_HASH})
        assert result.status is target


# 23

def test_23_terminal_state_finality():
    for terminal in (HypothesisStatus.REFUTED, HypothesisStatus.REVISED, HypothesisStatus.RETIRED):
        h = transition_hypothesis(_hypothesis(), terminal, {"reason": "final"})
        for target in HypothesisStatus:
            with pytest.raises(HypothesisTransitionError):
                transition_hypothesis(h, target, {"reason": "reactivate"})


# 24

def test_24_illegal_transition_rejected():
    h = _hypothesis()
    with pytest.raises(HypothesisTransitionError):
        transition_hypothesis(h, HypothesisStatus.ACTIVE, {"reason": "noop"})
    supported = transition_hypothesis(h, HypothesisStatus.SUPPORTED, {"reason": "support"})
    assert transition_hypothesis(supported, HypothesisStatus.REFUTED, {"reason": "refutation"}).status is HypothesisStatus.REFUTED


# 25

def test_25_transition_reason_required():
    with pytest.raises(HypothesisTransitionError):
        transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {})


# 26

def test_26_parent_hypothesis_must_exist():
    h = _hypothesis(parent_hypothesis_hash=VALID_HASH)
    with pytest.raises(HypothesisIntegrityError):
        h.verify()


# 27

def test_27_parent_hash_integrity_verified():
    parent = transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {"reason": "evidence"})
    child = _hypothesis(parent=parent)
    assert child.verify(parent=parent)
    forged = transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {"reason": "different"})
    with pytest.raises(HypothesisIntegrityError):
        child.verify(parent=forged)


# 28

def test_28_descendant_cannot_rewrite_ancestor():
    parent = transition_hypothesis(_hypothesis(source={"observation": "A"}), HypothesisStatus.REFUTED, {"reason": "refuted"})
    child = _hypothesis(parent=parent, source={"observation": "B"})
    assert parent.formulation == "The system is deterministic."
    assert child.parent_hypothesis_hash == parent.hypothesis_hash
    assert child.hypothesis_hash != parent.hypothesis_hash
    assert parent.status is HypothesisStatus.REFUTED


# 29

def test_29_recursive_lineage_preserved():
    root = transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {"reason": "r1"})
    child = transition_hypothesis(_hypothesis(parent=root), HypothesisStatus.REVISED, {"reason": "r2"})
    grandchild = _hypothesis(parent=child)
    assert child.parent_hypothesis_hash == root.hypothesis_hash
    assert grandchild.parent_hypothesis_hash == child.hypothesis_hash
    assert grandchild.parent_hypothesis_hash != root.hypothesis_hash
    assert child.verify(parent=root)
    assert grandchild.verify(parent=child)


# 30

def test_30_transition_history_tampering_detected():
    h = transition_hypothesis(_hypothesis(), HypothesisStatus.REFUTED, {"reason": "real"})
    exported = dict(h.export())
    tampered_history = list(exported["transition_history"])
    tampered_history[0] = dict(tampered_history[0])
    tampered_history[0]["reason"] = {"reason": "forged"}
    with pytest.raises(HypothesisIntegrityError):
        HypothesisRecord(
            exported["formulation"], exported["hypothesis_type"], exported["source"],
            exported["parent_hypothesis_hash"], tuple(exported["claim_hashes"]),
            tuple(exported["evidence_hashes"]), exported["status"],
            tuple(tampered_history), exported["hypothesis_hash"],
        )


# 31

def test_31_cross_runtime_byte_identical_reproduction():
    h = _hypothesis(source={"z": [3, 2], "a": "stable"})
    expected = hashlib.sha256(canonical_bytes(h.export())).hexdigest()
    code = (
        "import sys,hashlib; sys.path.insert(0,'src'); "
        "from jamp.research.hypothesis import make_hypothesis; "
        "from jamp.research.canonical import canonical_bytes; "
        "h=make_hypothesis(formulation='The system is deterministic.', "
        "hypothesis_type='SCIENTIFIC', source={'z':[3,2],'a':'stable'}); "
        "print(hashlib.sha256(canonical_bytes(h.export())).hexdigest())"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == expected


# 32

def test_32_zero_io_network_domain_contamination():
    import jamp.research.hypothesis as module

    source = inspect.getsource(module)
    forbidden = ("import socket", "import requests", "import urllib", "import httpx", "jamp.domain", "open(", "Path(", "os.environ")
    assert not any(token in source for token in forbidden)
    assert "runtime metadata" in source
    assert "canonical_bytes" in source
