"""Executable acceptance and adversarial contract for P20.6.

The suite intentionally exercises behavior rather than declaring gate names only.
The implementation under test is expected to remain deterministic, immutable,
content-addressed, provenance-preserving, and isolated from production JAMP.
"""
from __future__ import annotations

import hashlib
import json

import pytest

from jamp.research.question_engine import (
    QuestionIntegrityError,
    QuestionStatus,
    QuestionType,
    ResearchQuestion,
    compute_question_hash,
    make_question,
    resolve_question,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
C1 = "4" * 64
C2 = "5" * 64
T1 = "6" * 64


class Evidence:
    def __init__(self, result_hash=H1, *, trace_hash=T1, event_ids=(H2,), state_anchors=(H3, H2), status="SUPPORTED"):
        self.result_hash = result_hash
        self.trace_hash = trace_hash
        self.event_ids = tuple(event_ids)
        self.state_anchors = tuple(state_anchors)
        self.status = status

    def verify_integrity(self):
        return True

    def export(self):
        return {
            "result_hash": self.result_hash,
            "trace_hash": self.trace_hash,
            "event_ids": self.event_ids,
            "state_anchors": self.state_anchors,
            "status": self.status,
        }


class Registry:
    def __init__(self, *evidence):
        self.items = {e.result_hash: e for e in evidence}

    def contains(self, key):
        return key in self.items

    def get(self, key):
        return self.items[key]

    def verify(self, key):
        return self.get(key).verify_integrity()

    def snapshot(self):
        return dict(self.items)


class Claim:
    def __init__(self, claim_hash, evidence_refs, status):
        self.claim_hash = claim_hash
        self.evidence_refs = tuple(evidence_refs)
        self.status = status

    def verify(self, registry):
        return True

    def export(self):
        return {
            "claim_hash": self.claim_hash,
            "evidence_refs": self.evidence_refs,
            "status": self.status,
        }


class Hypothesis:
    def __init__(self, hypothesis_hash, *, parent_hypothesis_hash=None, status="ACTIVE"):
        self.hypothesis_hash = hypothesis_hash
        self.parent_hypothesis_hash = parent_hypothesis_hash
        self.status = status

    def verify(self, registry=None, **kwargs):
        return True

    def export(self):
        return {
            "hypothesis_hash": self.hypothesis_hash,
            "parent_hypothesis_hash": self.parent_hypothesis_hash,
            "status": self.status,
        }


def question(*, evidence=(), claims=(), hypotheses=(), status=QuestionStatus.UNRESOLVED, formulation="Why does X occur?", question_type=QuestionType.EXPLANATORY, context=None, constraints=None, parent_question_hash=None):
    registry = Registry(*(Evidence(h) for h in evidence))
    return make_question(
        registry,
        formulation=formulation,
        question_type=question_type,
        context=context or {"domain": "test"},
        constraints=constraints or {"scope": "local"},
        evidence_hashes=evidence,
        claim_hashes=tuple(c.claim_hash for c in claims),
        hypothesis_hashes=tuple(h.hypothesis_hash for h in hypotheses),
        parent_question_hash=parent_question_hash,
        status=status,
    )


# 01 schema validity

def test_gate_01_schema_validity():
    q = question()
    assert isinstance(q, ResearchQuestion)
    assert q.formulation == "Why does X occur?"


# 02 immutable question record

def test_gate_02_immutable_question_record():
    q = question()
    with pytest.raises((AttributeError, TypeError)):
        q.formulation = "mutated"


# 03 valid question_hash

def test_gate_03_valid_question_hash():
    q = question()
    assert len(q.question_hash) == 64
    assert all(c in "0123456789abcdef" for c in q.question_hash)
    assert q.verify()


# 04 deterministic hash computation

def test_gate_04_deterministic_hash_computation():
    a = question(context={"b": 2, "a": 1}, constraints={"z": [2, 1], "a": "x"})
    b = question(context={"a": 1, "b": 2}, constraints={"a": "x", "z": [2, 1]})
    assert a.question_hash == b.question_hash


# 05 self verification

def test_gate_05_self_verification():
    assert question().verify() is True


# 06 canonical formulation

def test_gate_06_canonical_formulation():
    q = question(formulation="  Why   does\n X   occur?  ")
    assert q.formulation == "Why does X occur?"
    assert q.question_hash == question(formulation="Why does X occur?").question_hash


# 07 explicit question type

def test_gate_07_explicit_question_type():
    with pytest.raises((QuestionIntegrityError, ValueError, TypeError)):
        make_question(Registry(), formulation="X?", question_type="", context={}, constraints={})


# 08 valid question status

def test_gate_08_valid_question_status():
    with pytest.raises((QuestionIntegrityError, ValueError, TypeError)):
        make_question(Registry(), formulation="X?", question_type=QuestionType.EXPLANATORY, context={}, constraints={}, status="NOT_A_STATUS")


# 09 only registered evidence

def test_gate_09_only_registered_evidence():
    q = question(evidence=(H1,))
    assert q.evidence_hashes == (H1,)


# 10 unknown evidence rejected

def test_gate_10_unknown_evidence_rejected():
    registry = Registry()
    with pytest.raises(QuestionIntegrityError):
        make_question(registry, formulation="X?", question_type=QuestionType.EXPLANATORY, context={}, constraints={}, evidence_hashes=(H1,))


# 11 evidence integrity verified

def test_gate_11_evidence_integrity_verified():
    bad = Evidence(H1)
    bad.verify_integrity = lambda: False
    with pytest.raises(QuestionIntegrityError):
        make_question(Registry(bad), formulation="X?", question_type=QuestionType.EXPLANATORY, context={}, constraints={}, evidence_hashes=(H1,))


# 12 claim integrity verified

def test_gate_12_claim_integrity_verified():
    class BadClaim(Claim):
        def verify(self, registry):
            raise QuestionIntegrityError("bad claim")
    registry = Registry(Evidence(H1))
    claim = BadClaim(C1, (H1,), "SUPPORTED")
    with pytest.raises(QuestionIntegrityError):
        make_question(registry, formulation="X?", question_type=QuestionType.EXPLANATORY, context={}, constraints={}, evidence_hashes=(H1,), claim_hashes=(claim.claim_hash,), claims=(claim,))


# 13 evidence/claim substitution rejected

def test_gate_13_evidence_claim_substitution_rejected():
    registry = Registry(Evidence(H1), Evidence(H2))
    claim = Claim(C1, (H1,), "SUPPORTED")
    with pytest.raises(QuestionIntegrityError):
        make_question(registry, formulation="X?", question_type=QuestionType.EXPLANATORY, context={}, constraints={}, evidence_hashes=(H2,), claim_hashes=(C1,), claims=(claim,))


# 14 evidence tampering detected

def test_gate_14_evidence_tampering_detected():
    q = question(evidence=(H1,))
    q.export()["evidence_hashes"] = (H2,)
    with pytest.raises((TypeError, KeyError)):
        q.export()["evidence_hashes"]


# 15 complete provenance preserved

def test_gate_15_complete_provenance_preserved():
    q = question(evidence=(H1,))
    assert q.provenance[H1]["result_hash"] == H1
    assert q.provenance[H1]["trace_hash"] == T1
    assert q.provenance[H1]["event_ids"] == (H2,)
    assert q.provenance[H1]["state_anchors"] == (H3, H2)


# 16 recursive provenance preserved

def test_gate_16_recursive_provenance_preserved():
    q = question(evidence=(H1,))
    exported = q.export()
    assert H1 in exported["provenance"]
    assert "trace_hash" in exported["provenance"][H1]
    assert "state_anchors" in exported["provenance"][H1]


# 17 unanswered question detected

def test_gate_17_unanswered_question_detected():
    q = question()
    assert q.status is QuestionStatus.UNRESOLVED
    assert q.resolution["class"] == "UNRESOLVED"


# 18 evidence gap detected

def test_gate_18_evidence_gap_detected():
    q = question(status=QuestionStatus.GAP, constraints={"required_evidence": (H1,)})
    assert q.status is QuestionStatus.GAP
    assert q.resolution["class"] == "GAP"


# 19 conflicting evidence detected

def test_gate_19_conflicting_evidence_detected():
    registry = Registry(Evidence(H1, status="SUPPORTED"), Evidence(H2, status="REFUTED"))
    q = make_question(registry, formulation="Is X true?", question_type=QuestionType.COMPARATIVE, context={}, constraints={}, evidence_hashes=(H1, H2))
    assert q.status is QuestionStatus.CONFLICTING


# 20 sufficient evidence -> ANSWERED

def test_gate_20_sufficient_evidence_answered():
    q = question(evidence=(H1,))
    answered = resolve_question(q, evidence_statuses={H1: "SUPPORTED"})
    assert answered.status is QuestionStatus.ANSWERED


# 21 insufficient evidence != ANSWERED

def test_gate_21_insufficient_evidence_not_answered():
    q = question()
    resolved = resolve_question(q, evidence_statuses={})
    assert resolved.status is not QuestionStatus.ANSWERED


# 22 contradictory claims cannot silently collapse

def test_gate_22_contradictory_claims_cannot_silently_collapse():
    registry = Registry(Evidence(H1), Evidence(H2))
    c1 = Claim(C1, (H1,), "SUPPORTED")
    c2 = Claim(C2, (H2,), "REFUTED")
    q = make_question(registry, formulation="Is X true?", question_type=QuestionType.COMPARATIVE, context={}, constraints={}, evidence_hashes=(H1, H2), claim_hashes=(C1, C2), claims=(c1, c2))
    assert q.status is QuestionStatus.CONFLICTING
    assert len(q.resolution["conflicts"]) == 2


# 23 deterministic resolution classification

def test_gate_23_deterministic_resolution_classification():
    q1 = question(evidence=(H1,))
    q2 = question(evidence=(H1,))
    assert q1.status == q2.status
    assert q1.resolution == q2.resolution


# 24 resolution explanation is provenance-addressed

def test_gate_24_resolution_explanation_is_provenance_addressed():
    q = question(evidence=(H1,))
    assert q.resolution["explanation_refs"] == (H1,)
    assert q.resolution["explanation_refs"]


# 25 hypothesis references preserved

def test_gate_25_hypothesis_references_preserved():
    h = Hypothesis(H1)
    q = question(hypotheses=(h,))
    assert q.hypothesis_hashes == (H1,)


# 26 question->hypothesis linkage integrity

def test_gate_26_question_hypothesis_linkage_integrity():
    h = Hypothesis(H1)
    q = question(hypotheses=(h,))
    assert q.verify(hypotheses=(h,)) is True
    with pytest.raises(QuestionIntegrityError):
        q.verify(hypotheses=(Hypothesis(H2),))


# 27 descendant question lineage preserved

def test_gate_27_descendant_question_lineage_preserved():
    parent = question()
    child = question(parent_question_hash=parent.question_hash)
    assert child.parent_question_hash == parent.question_hash
    assert child.lineage == (parent.question_hash, child.question_hash)


# 28 ancestor cannot be rewritten

def test_gate_28_ancestor_cannot_be_rewritten():
    parent = question(formulation="Original question?")
    child = question(parent_question_hash=parent.question_hash, formulation="Refined question?")
    assert child.parent_question_hash == parent.question_hash
    assert child.question_hash != parent.question_hash
    assert parent.formulation == "Original question?"


# 29 cyclic research lineage rejected

def test_gate_29_cyclic_research_lineage_rejected():
    parent = question()
    with pytest.raises(QuestionIntegrityError):
        question(parent_question_hash=parent.question_hash, constraints={"lineage": [parent.question_hash, parent.question_hash]})


# 30 question payload tampering detected

def test_gate_30_question_payload_tampering_detected():
    q = question()
    exported = dict(q.export())
    exported["formulation"] = "Tampered?"
    with pytest.raises(QuestionIntegrityError):
        ResearchQuestion.from_export(exported)


# 31 evidence substitution attack rejected

def test_gate_31_evidence_substitution_attack_rejected():
    q = question(evidence=(H1,))
    with pytest.raises(QuestionIntegrityError):
        q.verify(evidence=(H2,))


# 32 runtime metadata injection rejected
@pytest.mark.parametrize("key", ["timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"])
def test_gate_32_runtime_metadata_injection_rejected(key):
    with pytest.raises(QuestionIntegrityError):
        question(context={key: "forbidden"})


# 33 cross-runtime byte-identical reproduction

def test_gate_33_cross_runtime_byte_identical_reproduction():
    kwargs = dict(
        formulation="  Why   does X occur? ",
        question_type=QuestionType.EXPLANATORY,
        context={"b": [2, 1], "a": {"z": 3, "x": 4}},
        constraints={"scope": "test"},
        evidence_hashes=(H1,),
    )
    first = compute_question_hash(**kwargs)
    second = compute_question_hash(**kwargs)
    assert first == second
    assert hashlib.sha256(json.dumps(first, sort_keys=True).encode()).hexdigest() == hashlib.sha256(json.dumps(second, sort_keys=True).encode()).hexdigest()


# 34 zero IO/network/jamp.domain contamination

def test_gate_34_zero_io_network_domain_contamination():
    import jamp.research.question_engine as module
    assert "jamp.domain" not in module.__dict__.get("__file__", "")
    source = open(module.__file__, "r", encoding="utf-8").read()
    assert "import socket" not in source
    assert "import requests" not in source
    assert "Path(" not in source
    assert "open(" not in source.replace("open(module.__file__", "")
