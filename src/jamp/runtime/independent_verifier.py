"""Stateless independent verification of JAMP's signed verdict chain.

The verifier does not call UniversalVerdict.is_confirmed() and never reads
persistence. Callers provide raw evidence and exported JSONL records.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Any

from jamp.runtime.universal_verdict import compute_jamp_verdict_hash
from jamp.runtime.verdict import JampVerdict

GENESIS_HASH = "sha256:" + "0" * 64
_CHAIN_METADATA_KEYS = frozenset({"prev_hash", "record_hash"})
_REQUIRED_STORES = ("traces", "verdicts", "universal_verdicts")


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class VerificationReport:
    verdict: str
    reproducible: bool
    checks: tuple[CheckResult, ...]
    reasons: tuple[str, ...]


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _skip_remaining(checks: list[CheckResult], names: tuple[str, ...], detail: str) -> None:
    existing = {check.name for check in checks}
    for name in names:
        if name not in existing:
            checks.append(CheckResult(name, "SKIP", detail))


def _report(checks: list[CheckResult], reasons: list[str], verdict: str) -> VerificationReport:
    return VerificationReport(
        verdict=verdict,
        reproducible=verdict == "VERIFIED",
        checks=tuple(checks),
        reasons=tuple(reasons),
    )


def _structure_is_valid(envelope: Any, jamp_verdict: Any, trace: Any) -> tuple[bool, str]:
    if not all(isinstance(item, dict) for item in (envelope, jamp_verdict, trace)):
        return False, "envelope, jamp_verdict and trace must be JSON objects"

    required_jv = {
        "trace_id",
        "status",
        "provider_model_id",
        "evidence_hash",
        "timestamp",
        "execution_status",
        "model_verification",
        "claims",
        "aggregate_status",
        "critical_unverified",
        "signature",
    }
    if not required_jv.issubset(jamp_verdict):
        return False, "jamp_verdict is missing required fields"
    if not isinstance(jamp_verdict.get("trace_id"), str) or not jamp_verdict["trace_id"]:
        return False, "jamp_verdict.trace_id must be a non-empty string"
    if not isinstance(jamp_verdict.get("signature"), str):
        return False, "jamp_verdict.signature must be a string"
    if not isinstance(jamp_verdict.get("claims"), list) or not all(
        isinstance(item, dict) for item in jamp_verdict["claims"]
    ):
        return False, "jamp_verdict.claims must be a list of objects"
    if not isinstance(jamp_verdict.get("critical_unverified"), list) or not all(
        isinstance(item, str) for item in jamp_verdict["critical_unverified"]
    ):
        return False, "jamp_verdict.critical_unverified must be a list of strings"

    if not isinstance(trace.get("trace_id"), str) or not trace["trace_id"]:
        return False, "trace.trace_id must be a non-empty string"
    if not isinstance(trace.get("execution_details"), dict):
        return False, "trace.execution_details must be an object"

    required_envelope = {"trace_id", "universal_verdict", "verdict_hash", "signature"}
    if not required_envelope.issubset(envelope):
        return False, "envelope is missing required fields"
    if not isinstance(envelope.get("trace_id"), str) or not envelope["trace_id"]:
        return False, "envelope.trace_id must be a non-empty string"
    if not isinstance(envelope.get("verdict_hash"), str) or not isinstance(
        envelope.get("signature"), str
    ):
        return False, "envelope hash and signature must be strings"

    uv_payload = envelope.get("universal_verdict")
    if not isinstance(uv_payload, dict):
        return False, "envelope.universal_verdict must be an object"
    required_uv = {
        "spec_ref",
        "criteria_ref",
        "execution_ref",
        "evidence_refs",
        "classification",
        "verdict",
        "verifier",
        "timestamp",
    }
    if not required_uv.issubset(uv_payload):
        return False, "universal_verdict is missing required fields"

    for section, keys in (
        ("spec_ref", ("spec_id", "spec_hash")),
        ("criteria_ref", ("criteria_id", "criteria_hash")),
        ("execution_ref", ("jamp_verdict_hash", "execution_status")),
        ("classification", ("label", "classification_hash")),
        ("verdict", ("result",)),
        ("verifier", ("version", "reproducible", "aggregation_rule_hash")),
    ):
        value = uv_payload.get(section)
        if not isinstance(value, dict) or not all(
            isinstance(value.get(key), str) for key in keys if key != "reproducible"
        ):
            return False, f"universal_verdict.{section} has invalid fields"
        if section == "verifier" and not isinstance(value.get("reproducible"), bool):
            return False, "universal_verdict.verifier.reproducible must be boolean"

    refs = uv_payload.get("evidence_refs")
    if not isinstance(refs, list):
        return False, "universal_verdict.evidence_refs must be a list"
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict) or not all(
            isinstance(ref.get(key), str) for key in ("type", "ref_hash", "source_sha256")
        ):
            return False, f"evidence_refs[{index}] has invalid fields"
    if not isinstance(uv_payload.get("timestamp"), str):
        return False, "universal_verdict.timestamp must be a string"

    return True, ""


def _verify_exported_chains(
    chain_records: dict[str, list[dict[str, Any]]],
    *,
    envelope: dict[str, Any],
    jamp_verdict: dict[str, Any],
    trace: dict[str, Any],
) -> tuple[bool, str]:
    expected_payloads = {
        "traces": trace,
        "verdicts": jamp_verdict,
        "universal_verdicts": envelope,
    }

    for store_name in _REQUIRED_STORES:
        records = chain_records.get(store_name)
        if not isinstance(records, list) or not records:
            return False, f"chain_records.{store_name} must be a non-empty list"

        previous_hash = GENESIS_HASH
        chain_started = False
        matching_record_found = False

        for index, record in enumerate(records):
            if not isinstance(record, dict):
                return False, f"{store_name}[{index}] is not an object"

            has_prev = "prev_hash" in record
            has_hash = "record_hash" in record
            if not has_prev and not has_hash:
                if chain_started:
                    return False, f"{store_name}[{index}] is legacy data after chain start"
                continue
            if not has_prev or not has_hash:
                return False, f"{store_name}[{index}] has incomplete chain metadata"

            chain_started = True
            if record.get("prev_hash") != previous_hash:
                return False, f"{store_name}[{index}] prev_hash does not match prior record"

            body = {key: value for key, value in record.items() if key != "record_hash"}
            try:
                expected_hash = "sha256:" + hashlib.sha256(_canonical_bytes(body)).hexdigest()
            except (TypeError, ValueError, OverflowError, UnicodeError):
                return False, f"{store_name}[{index}] cannot be canonicalized"
            if not hmac.compare_digest(str(record.get("record_hash")), expected_hash):
                return False, f"{store_name}[{index}] record_hash mismatch"
            previous_hash = expected_hash

            public_record = {
                key: value for key, value in record.items() if key not in _CHAIN_METADATA_KEYS
            }
            expected = expected_payloads[store_name]
            if store_name == "universal_verdicts":
                expected = {**expected, "trace_id": trace["trace_id"]}
            if public_record == expected:
                matching_record_found = True

        if not chain_started:
            return False, f"{store_name} contains no verifiable hash-chain records"
        if not matching_record_found:
            return False, f"{store_name} has no chain record matching the supplied object"

    return True, "all three exported stores are hash-valid and bound to the supplied objects"


def verify_chain(
    *,
    envelope: dict[str, Any],
    jamp_verdict: dict[str, Any],
    trace: dict[str, Any],
    evidence_files: dict[str, bytes] | None = None,
    chain_records: dict[str, list[dict[str, Any]]] | None = None,
    secret: bytes | None = None,
) -> VerificationReport:
    """Verify signatures, object links, raw evidence and exported JSONL chains."""
    checks: list[CheckResult] = []
    reasons: list[str] = []
    names = (
        "secret",
        "object_structure",
        "trace_linkage",
        "jamp_signature",
        "jamp_verdict_hash",
        "envelope_hash",
        "envelope_signature",
        "classification_consistency",
        "aggregate_consistency",
        "output_digest",
        "evidence_content",
        "persistence_chain",
    )

    if not isinstance(secret, bytes) or not secret:
        checks.append(CheckResult("secret", "FAIL", "shared HMAC secret is missing"))
        reasons.append("shared HMAC secret is required")
        _skip_remaining(checks, names[1:], "verification stopped because the secret is unavailable")
        return _report(checks, reasons, "REFUSE")
    checks.append(CheckResult("secret", "PASS", "shared HMAC secret supplied"))

    valid, detail = _structure_is_valid(envelope, jamp_verdict, trace)
    if not valid:
        checks.append(CheckResult("object_structure", "FAIL", detail))
        reasons.append(detail)
        _skip_remaining(
            checks, names[2:], "verification stopped because input structure is invalid"
        )
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(CheckResult("object_structure", "PASS", "required fields and types are valid"))

    trace_id = trace["trace_id"]
    if not (trace_id == jamp_verdict["trace_id"] == envelope["trace_id"]):
        checks.append(CheckResult("trace_linkage", "FAIL", "trace_id values do not match"))
        reasons.append("trace_id mismatch across trace, JampVerdict and envelope")
        _skip_remaining(checks, names[3:], "verification stopped after trace linkage failure")
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(CheckResult("trace_linkage", "PASS", f"all objects reference {trace_id}"))

    try:
        jv = JampVerdict.from_dict(jamp_verdict)
        jv_valid = jv.verify(secret.decode("utf-8"))
    except (UnicodeDecodeError, KeyError, TypeError, ValueError, OverflowError, AttributeError):
        jv_valid = False
        jv = None
    if not jv_valid or jv is None:
        checks.append(CheckResult("jamp_signature", "FAIL", "JampVerdict HMAC is invalid"))
        reasons.append("JampVerdict signature verification failed")
        _skip_remaining(
            checks, names[4:], "verification stopped after JampVerdict signature failure"
        )
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(CheckResult("jamp_signature", "PASS", "JampVerdict HMAC-SHA256 is valid"))

    try:
        actual_jamp_hash = compute_jamp_verdict_hash(jv)
    except (TypeError, ValueError, OverflowError):
        actual_jamp_hash = ""
    expected_jamp_hash = envelope["universal_verdict"]["execution_ref"].get("jamp_verdict_hash")
    if not actual_jamp_hash or actual_jamp_hash != expected_jamp_hash:
        checks.append(CheckResult("jamp_verdict_hash", "FAIL", "JampVerdict payload hash mismatch"))
        reasons.append("execution_ref.jamp_verdict_hash does not match the supplied JampVerdict")
        _skip_remaining(checks, names[5:], "verification stopped after JampVerdict hash failure")
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(
        CheckResult("jamp_verdict_hash", "PASS", "JampVerdict canonical payload hash matches")
    )

    try:
        from jamp.api.app import _universal_verdict_from_dict

        uv = _universal_verdict_from_dict(envelope["universal_verdict"])
        actual_envelope_hash = uv.compute_verdict_hash()
    except (ImportError, TypeError, ValueError, KeyError, OverflowError, AttributeError):
        uv = None
        actual_envelope_hash = ""
    if uv is None or actual_envelope_hash != envelope["verdict_hash"]:
        checks.append(
            CheckResult("envelope_hash", "FAIL", "UniversalVerdict canonical hash mismatch")
        )
        reasons.append(
            "UniversalVerdict canonical payload hash does not match envelope.verdict_hash"
        )
        _skip_remaining(checks, names[6:], "verification stopped after envelope hash failure")
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(CheckResult("envelope_hash", "PASS", "complete canonical payload hash matches"))

    try:
        signature_valid = uv.verify(secret, envelope["signature"])
    except (TypeError, ValueError):
        signature_valid = False
    if not signature_valid:
        checks.append(CheckResult("envelope_signature", "FAIL", "UniversalVerdict HMAC is invalid"))
        reasons.append("UniversalVerdict signature verification failed")
        _skip_remaining(checks, names[7:], "verification stopped after envelope signature failure")
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(
        CheckResult("envelope_signature", "PASS", "UniversalVerdict HMAC-SHA256 is valid")
    )

    stored_classification_hash = envelope["universal_verdict"]["classification"].get(
        "classification_hash"
    )
    if (
        uv.classification.label != uv.verdict.result
        or stored_classification_hash != uv.classification.classification_hash
    ):
        checks.append(
            CheckResult(
                "classification_consistency",
                "FAIL",
                "classification label/result or derived classification hash mismatch",
            )
        )
        reasons.append(
            "classification label must equal verdict result and its stored hash must match"
        )
        _skip_remaining(checks, names[8:], "verification stopped after classification mismatch")
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(
        CheckResult("classification_consistency", "PASS", "classification label matches result")
    )

    if uv.verdict.result != jv.aggregate_status:
        checks.append(
            CheckResult(
                "aggregate_consistency", "FAIL", "UniversalVerdict result differs from aggregate"
            )
        )
        reasons.append("UniversalVerdict result does not equal JampVerdict aggregate_status")
        _skip_remaining(checks, names[9:], "verification stopped after aggregate mismatch")
        return _report(checks, reasons, "CONTRADICTED")
    checks.append(
        CheckResult("aggregate_consistency", "PASS", "verdict result matches aggregate_status")
    )

    execution_details = trace["execution_details"]
    if "output_digest" not in execution_details:
        checks.append(
            CheckResult("output_digest", "SKIP", "trace has no execution_details.output_digest")
        )
        reasons.append("output digest is unavailable")
    else:
        output_digest = execution_details["output_digest"]
        if (
            not isinstance(output_digest, str)
            or not output_digest
            or jv.evidence_hash != output_digest
        ):
            checks.append(
                CheckResult(
                    "output_digest",
                    "FAIL",
                    "JampVerdict evidence_hash differs from output_digest",
                )
            )
            reasons.append("JampVerdict evidence_hash does not match trace output_digest")
            _skip_remaining(checks, names[10:], "verification stopped after output digest mismatch")
            return _report(checks, reasons, "CONTRADICTED")
        checks.append(
            CheckResult("output_digest", "PASS", "JampVerdict output digest matches trace")
        )

    refs = uv.evidence_refs
    if evidence_files is not None and not isinstance(evidence_files, dict):
        checks.append(
            CheckResult(
                "evidence_content",
                "FAIL",
                "evidence_files must be a mapping of hashes to bytes",
            )
        )
        reasons.append("evidence_files has invalid structure")
        _skip_remaining(
            checks, names[11:], "verification stopped after evidence_files structure failure"
        )
        return _report(checks, reasons, "CONTRADICTED")
    if not refs:
        checks.append(CheckResult("evidence_content", "SKIP", "no evidence_refs were supplied"))
        reasons.append("raw evidence references are absent")
    elif evidence_files is None:
        checks.append(
            CheckResult("evidence_content", "SKIP", "raw evidence files were not supplied")
        )
        reasons.append("raw evidence content is unavailable")
    else:
        evidence_error = ""
        for ref in refs:
            source_hash = ref.source_sha256
            raw = evidence_files.get(source_hash)
            if not isinstance(raw, bytes):
                evidence_error = f"raw bytes missing for {source_hash}"
                break
            actual_source_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
            if not hmac.compare_digest(actual_source_hash, source_hash):
                evidence_error = f"raw evidence hash mismatch for {source_hash}"
                break
        if evidence_error:
            checks.append(CheckResult("evidence_content", "FAIL", evidence_error))
            reasons.append(evidence_error)
            _skip_remaining(
                checks, names[11:], "verification stopped after evidence content failure"
            )
            return _report(checks, reasons, "CONTRADICTED")
        checks.append(
            CheckResult("evidence_content", "PASS", "all referenced raw evidence hashes match")
        )

    if chain_records is None:
        checks.append(
            CheckResult("persistence_chain", "SKIP", "exported chain_records were not supplied")
        )
        reasons.append("persistence-chain continuity was not independently checked")
    elif not isinstance(chain_records, dict):
        checks.append(CheckResult("persistence_chain", "FAIL", "chain_records must be an object"))
        reasons.append("chain_records has invalid structure")
        return _report(checks, reasons, "CONTRADICTED")
    else:
        chain_valid, chain_detail = _verify_exported_chains(
            chain_records, envelope=envelope, jamp_verdict=jamp_verdict, trace=trace
        )
        checks.append(
            CheckResult("persistence_chain", "PASS" if chain_valid else "FAIL", chain_detail)
        )
        if not chain_valid:
            reasons.append(chain_detail)
            return _report(checks, reasons, "CONTRADICTED")

    if all(check.status == "PASS" for check in checks):
        return _report(checks, reasons, "VERIFIED")
    return _report(checks, reasons, "INCONCLUSIVE")


def report_to_dict(report: VerificationReport) -> dict[str, Any]:
    """Serialize the immutable report into the public JSON response shape."""
    return asdict(report)
