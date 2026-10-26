"""Signed claim-level JAMP verdicts with deterministic aggregation."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Claim:
    """One bounded claim and the evidence status assigned to it."""

    text: str
    type: str
    source: str | None
    status: str
    evidence: dict[str, Any] | None = None
    reason: str | None = None
    critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _claim_value(claim: Claim | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(claim, Claim):
        return getattr(claim, key, default)
    if isinstance(claim, dict):
        return claim.get(key, default)
    return default


def aggregate_verdict(claims: list[Claim | dict[str, Any]]) -> str:
    """Aggregate claim statuses without allowing an unverified claim to become VERIFIED."""
    if not claims:
        return "PARTIAL"
    statuses = [str(_claim_value(claim, "status", "INCONCLUSIVE")) for claim in claims]
    if any(status in {"CONTRADICTED", "E4_CONTRADICTED"} for status in statuses):
        return "CONTRADICTED"
    if any(
        bool(_claim_value(claim, "critical", False))
        and status not in {"VERIFIED", "E4_VERIFIED"}
        for claim, status in zip(claims, statuses, strict=True)
    ):
        return "INCONCLUSIVE"
    if all(status in {"VERIFIED", "E4_VERIFIED"} for status in statuses):
        return "VERIFIED"
    return "PARTIAL"


def critical_unverified_claims(claims: list[Claim | dict[str, Any]]) -> list[str]:
    """Return text for critical claims that have not been verified."""
    return [
        str(_claim_value(claim, "text", ""))
        for claim in claims
        if bool(_claim_value(claim, "critical", False))
        and _claim_value(claim, "status", "INCONCLUSIVE") not in {"VERIFIED", "E4_VERIFIED"}
    ]


@dataclass(frozen=True)
class JampVerdict:
    """A signed verdict bound to execution, model provenance, and individual claims."""

    trace_id: str
    status: str
    provider_model_id: str | None
    evidence_hash: str
    timestamp: float
    signature: str | None = None
    execution_status: str = "EXECUTE"
    model_verification: str | None = None
    claims: list[Claim | dict[str, Any]] = field(default_factory=list)
    aggregate_status: str = "PARTIAL"
    critical_unverified: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.model_verification is None:
            object.__setattr__(self, "model_verification", self.status)

    def _payload(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "provider_model_id": self.provider_model_id,
            "evidence_hash": self.evidence_hash,
            "timestamp": self.timestamp,
            "execution_status": self.execution_status,
            "model_verification": self.model_verification,
            "claims": [
                claim.to_dict() if isinstance(claim, Claim) else claim for claim in self.claims
            ],
            "aggregate_status": self.aggregate_status,
            "critical_unverified": list(self.critical_unverified),
        }

    def sign(self, secret: str) -> JampVerdict:
        """Return a copy signed with HMAC-SHA256."""
        if not secret:
            raise ValueError("Signing secret must not be empty")
        payload_bytes = json.dumps(
            self._payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        return JampVerdict(**{**asdict(self), "signature": signature})

    def verify(self, secret: str) -> bool:
        """Verify the signature without timing-sensitive string comparison."""
        if not secret or not isinstance(self.signature, str):
            return False
        expected = self.sign(secret).signature
        return hmac.compare_digest(self.signature, expected or "")

    def to_dict(self) -> dict[str, Any]:
        payload = self._payload()
        payload["signature"] = self.signature
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> JampVerdict:
        """Parse the public verdict contract; accept older signed payload shapes."""
        if not isinstance(value, dict):
            raise ValueError("Verdict must be a JSON object")
        trace_id = value.get("trace_id")
        status = value.get("status")
        provider_model_id = value.get("provider_model_id")
        evidence_hash = value.get("evidence_hash")
        timestamp = value.get("timestamp")
        signature = value.get("signature")
        if not isinstance(trace_id, str) or not trace_id:
            raise ValueError("trace_id must be a non-empty string")
        if status not in {"VERIFIED", "CONTRADICTED", "INCONCLUSIVE"}:
            raise ValueError("Unsupported verdict status")
        if provider_model_id is not None and not isinstance(provider_model_id, str):
            raise ValueError("provider_model_id must be a string or null")
        if not isinstance(evidence_hash, str) or not evidence_hash:
            raise ValueError("evidence_hash must be a non-empty string")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("timestamp must be a number")
        if signature is not None and not isinstance(signature, str):
            raise ValueError("signature must be a string or null")
        claims = value.get("claims", [])
        if not isinstance(claims, list) or any(not isinstance(item, dict) for item in claims):
            raise ValueError("claims must be a list of objects")
        critical_unverified = value.get("critical_unverified", [])
        if not isinstance(critical_unverified, list) or any(
            not isinstance(item, str) for item in critical_unverified
        ):
            raise ValueError("critical_unverified must be a list of strings")
        execution_status = value.get("execution_status", "EXECUTE")
        model_verification = value.get("model_verification", status)
        aggregate_status = value.get("aggregate_status", "PARTIAL")
        if not isinstance(execution_status, str) or not isinstance(model_verification, str):
            raise ValueError("execution_status and model_verification must be strings")
        if aggregate_status not in {"VERIFIED", "CONTRADICTED", "INCONCLUSIVE", "PARTIAL"}:
            raise ValueError("Unsupported aggregate_status")
        return cls(
            trace_id=trace_id,
            status=status,
            provider_model_id=provider_model_id,
            evidence_hash=evidence_hash,
            timestamp=float(timestamp),
            signature=signature,
            execution_status=execution_status,
            model_verification=model_verification,
            claims=claims,
            aggregate_status=aggregate_status,
            critical_unverified=critical_unverified,
        )
