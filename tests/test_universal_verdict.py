from __future__ import annotations

import hashlib
import json

from jamp.runtime.universal_verdict import (
    CriteriaRef,
    EvidenceRef,
    ExecutionRef,
    SpecRef,
    UniversalClassification,
    UniversalVerdict,
    VerdictResult,
    VerifierInfo,
    compute_jamp_verdict_hash,
)
from jamp.runtime.verdict import JampVerdict


def _universal_verdict(
    *,
    result: str = "VERIFIED",
    reproducible: bool = True,
    evidence_refs: tuple[EvidenceRef, ...] = (),
    execution_ref: ExecutionRef | None = None,
) -> UniversalVerdict:
    return UniversalVerdict(
        spec_ref=SpecRef("spec.v0", "sha256:spec"),
        criteria_ref=CriteriaRef("criteria.v0", "sha256:criteria"),
        execution_ref=execution_ref or ExecutionRef("sha256:jamp-verdict", "EXECUTE"),
        evidence_refs=evidence_refs,
        classification=UniversalClassification("FACTUAL_CLAIM"),
        verdict=VerdictResult(result),
        verifier=VerifierInfo("uv0.1.0", reproducible, "sha256:aggregation-rules"),
        timestamp="2026-10-29T12:00:00Z",
    )


def test_compute_jamp_verdict_hash_is_deterministic_and_uses_sign_canonicalization():
    jv = JampVerdict(
        trace_id="trace_universal_v0",
        status="VERIFIED",
        provider_model_id="provider/model",
        evidence_hash="sha256:evidence",
        timestamp=1793275200.0,
    )
    payload = jv._payload()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )
    expected = "sha256:" + hashlib.sha256(canonical).hexdigest()

    assert compute_jamp_verdict_hash(jv) == expected
    assert compute_jamp_verdict_hash(jv) == compute_jamp_verdict_hash(jv)
    signed = jv.sign("test-signing-key")
    assert signed.verify("test-signing-key")
    assert signed._payload() == payload
    assert compute_jamp_verdict_hash(signed) == expected


def test_verdict_hash_is_deterministic_and_changes_when_result_changes():
    verdict = _universal_verdict()
    same = _universal_verdict()
    changed = _universal_verdict(result="CONTRADICTED")

    assert verdict.verdict.verdict_hash == verdict.compute_verdict_hash()
    assert verdict.verdict.verdict_hash == same.verdict.verdict_hash
    assert verdict.verdict.verdict_hash != changed.verdict.verdict_hash


def test_non_reproducible_verdict_can_be_signed_but_is_not_confirmed():
    verdict = _universal_verdict(result="VERIFIED", reproducible=False)
    signature = verdict.sign(b"test-signing-key")

    assert verdict.verify(b"test-signing-key", signature)
    assert not verdict.is_confirmed()


def test_evidence_refs_are_immutable_and_execution_jamp_verdict_is_not_modified():
    jv = JampVerdict(
        trace_id="trace_unchanged",
        status="VERIFIED",
        provider_model_id="provider/model",
        evidence_hash="sha256:evidence",
        timestamp=1793275200.0,
    )
    original_payload = jv._payload()
    jamp_hash = compute_jamp_verdict_hash(jv)
    evidence = EvidenceRef("api_response", "sha256:ref", "sha256:source")
    verdict = _universal_verdict(
        evidence_refs=(evidence,),
        execution_ref=ExecutionRef(jamp_hash, jv.execution_status),
    )

    assert isinstance(verdict.evidence_refs, tuple)
    assert verdict.evidence_refs == (evidence,)
    assert verdict.execution_ref.jamp_verdict_hash == jamp_hash
    assert jv._payload() == original_payload
    assert not hasattr(verdict.evidence_refs, "append")
