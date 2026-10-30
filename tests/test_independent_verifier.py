from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jamp.api.app import _universal_verdict_from_dict, create_app
from jamp.api.auth import require_api_key
from jamp.runtime.independent_verifier import GENESIS_HASH, verify_chain
from jamp.runtime.persistence import AuditPersistence
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

pytestmark = pytest.mark.real_auth

SECRET = b"track-4-test-shared-secret"
SECRET_TEXT = SECRET.decode("utf-8")
RAW_EVIDENCE = b"independent verifier raw evidence"


def _source_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _build_chain_record(payload: dict[str, Any]) -> dict[str, Any]:
    body = {**payload, "prev_hash": GENESIS_HASH}
    record_hash = "sha256:" + hashlib.sha256(
        json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    return {**body, "record_hash": record_hash}


def _valid_case() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, bytes],
    dict[str, list[dict[str, Any]]],
]:
    trace_id = "trace_independent_001"
    source_sha256 = _source_hash(RAW_EVIDENCE)
    jv = JampVerdict(
        trace_id=trace_id,
        status="VERIFIED",
        provider_model_id="provider/model",
        evidence_hash="sha256:" + "a" * 64,
        timestamp=1793361600.0,
        execution_status="EXECUTE",
        model_verification="VERIFIED",
        claims=[],
        aggregate_status="VERIFIED",
        critical_unverified=[],
    ).sign(SECRET_TEXT)
    jv_payload = jv.to_dict()
    trace = {
        "trace_id": trace_id,
        "execution_details": {"output_digest": jv_payload["evidence_hash"]},
    }
    uv = UniversalVerdict(
        spec_ref=SpecRef("spec.v0", "sha256:" + "1" * 64),
        criteria_ref=CriteriaRef("criteria.v0", "sha256:" + "2" * 64),
        execution_ref=ExecutionRef(compute_jamp_verdict_hash(jv), jv.execution_status),
        evidence_refs=(
            EvidenceRef("api_response", "sha256:" + "3" * 64, source_sha256),
        ),
        classification=UniversalClassification("VERIFIED"),
        verdict=VerdictResult("VERIFIED"),
        verifier=VerifierInfo("uv0.2.0", False, "sha256:" + "4" * 64),
        timestamp="2026-10-30T08:00:00Z",
    )
    envelope = {
        "trace_id": trace_id,
        "universal_verdict": uv.canonical_payload(),
        "verdict_hash": uv.compute_verdict_hash(),
        "signature": uv.sign(SECRET),
        "semantics": "test envelope",
    }
    evidence_files = {source_sha256: RAW_EVIDENCE}
    chain_records = {
        "traces": [_build_chain_record(trace)],
        "verdicts": [_build_chain_record(jv_payload)],
        "universal_verdicts": [_build_chain_record(envelope)],
    }
    return envelope, jv_payload, trace, evidence_files, chain_records


def _resign_envelope(envelope: dict[str, Any]) -> None:
    uv = _universal_verdict_from_dict(envelope["universal_verdict"])
    envelope["verdict_hash"] = uv.compute_verdict_hash()
    envelope["signature"] = uv.sign(SECRET)


def test_valid_full_chain_and_authenticated_endpoint_return_verified(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    envelope, jv, trace, evidence_files, chain_records = _valid_case()
    monkeypatch.setenv("JAMP_SIGNING_KEY", SECRET_TEXT)
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "test-api-key-hash-secret")

    audit_path = tmp_path / "audit.jsonl"
    unauthenticated = TestClient(create_app(audit_storage_path=audit_path))
    assert unauthenticated.post("/v1/verify-chain", json={}).status_code == 401

    app = create_app(audit_storage_path=audit_path)
    app.dependency_overrides[require_api_key] = lambda: None
    client = TestClient(app)
    response = client.post(
        "/v1/verify-chain",
        json={
            "envelope": envelope,
            "jamp_verdict": jv,
            "trace": trace,
            "evidence_files": {
                source_hash: base64.b64encode(raw).decode("ascii")
                for source_hash, raw in evidence_files.items()
            },
            "chain_records": chain_records,
        },
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["verdict"] == "VERIFIED"
    assert report["reproducible"] is True
    assert len(report["checks"]) == 12
    assert all(check["status"] == "PASS" for check in report["checks"])
    assert not audit_path.exists()
    assert not (tmp_path / "verdicts.jsonl").exists()
    assert not (tmp_path / "universal_verdicts.jsonl").exists()


def test_tampered_jamp_signature_is_contradicted() -> None:
    envelope, jv, trace, evidence_files, chain_records = _valid_case()
    jv["signature"] = "0" * 64

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=chain_records, secret=SECRET,
    )

    assert report.verdict == "CONTRADICTED"
    assert next(c for c in report.checks if c.name == "jamp_signature").status == "FAIL"


def test_tampered_envelope_signature_is_contradicted() -> None:
    envelope, jv, trace, evidence_files, chain_records = _valid_case()
    envelope["signature"] = "0" * 64

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=chain_records, secret=SECRET,
    )

    assert report.verdict == "CONTRADICTED"
    assert next(c for c in report.checks if c.name == "envelope_signature").status == "FAIL"


def test_tampered_envelope_verdict_hash_is_contradicted() -> None:
    envelope, jv, trace, evidence_files, chain_records = _valid_case()
    envelope["verdict_hash"] = "sha256:" + "0" * 64

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=chain_records, secret=SECRET,
    )

    assert report.verdict == "CONTRADICTED"
    assert next(c for c in report.checks if c.name == "envelope_hash").status == "FAIL"


def test_changed_evidence_reference_without_raw_files_is_inconclusive() -> None:
    envelope, jv, trace, _, _ = _valid_case()
    envelope["universal_verdict"]["evidence_refs"][0]["source_sha256"] = (
        "sha256:" + "b" * 64
    )
    _resign_envelope(envelope)

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace, evidence_files=None,
        chain_records=None, secret=SECRET,
    )

    assert report.verdict == "INCONCLUSIVE"
    assert next(c for c in report.checks if c.name == "evidence_content").status == "SKIP"


def test_changed_evidence_reference_with_raw_files_is_contradicted() -> None:
    envelope, jv, trace, evidence_files, _ = _valid_case()
    envelope["universal_verdict"]["evidence_refs"][0]["source_sha256"] = (
        "sha256:" + "b" * 64
    )
    _resign_envelope(envelope)

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=None, secret=SECRET,
    )

    assert report.verdict == "CONTRADICTED"
    assert next(c for c in report.checks if c.name == "evidence_content").status == "FAIL"


def test_broken_exported_chain_is_contradicted() -> None:
    envelope, jv, trace, evidence_files, chain_records = _valid_case()
    chain_records["traces"][0]["prev_hash"] = "sha256:" + "f" * 64

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=chain_records, secret=SECRET,
    )

    assert report.verdict == "CONTRADICTED"
    assert next(c for c in report.checks if c.name == "persistence_chain").status == "FAIL"


def test_missing_secret_returns_refuse(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("JAMP_ENV", "production")
    monkeypatch.delenv("JAMP_SIGNING_KEY", raising=False)
    monkeypatch.setenv("JAMP_API_KEY_HASH_SECRET", "test-api-key-hash-secret")
    app = create_app(audit_storage_path=tmp_path / "audit.jsonl")
    app.dependency_overrides[require_api_key] = lambda: None

    response = TestClient(app).post("/v1/verify-chain", json={})

    assert response.status_code == 200
    report = response.json()
    assert report["verdict"] == "REFUSE"
    assert report["reproducible"] is False
    assert report["checks"][0]["name"] == "secret"
    assert report["checks"][0]["status"] == "FAIL"


def test_trace_without_output_digest_is_inconclusive() -> None:
    envelope, jv, trace, evidence_files, _ = _valid_case()
    trace["execution_details"] = {}

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=None, secret=SECRET,
    )

    assert report.verdict == "INCONCLUSIVE"
    assert next(c for c in report.checks if c.name == "output_digest").status == "SKIP"


def test_verifier_never_calls_confirmation_or_storage_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope, jv, trace, evidence_files, chain_records = _valid_case()

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("forbidden confirmation or storage read")

    monkeypatch.setattr(UniversalVerdict, "is_confirmed", forbidden)
    monkeypatch.setattr(AuditPersistence, "read_trace_by_id", forbidden)
    monkeypatch.setattr(AuditPersistence, "read_verdict_by_id", forbidden)
    monkeypatch.setattr(AuditPersistence, "read_universal_verdict_by_id", forbidden)

    report = verify_chain(
        envelope=envelope, jamp_verdict=jv, trace=trace,
        evidence_files=evidence_files, chain_records=chain_records, secret=SECRET,
    )

    assert report.verdict == "VERIFIED"
    assert report.reproducible is True
