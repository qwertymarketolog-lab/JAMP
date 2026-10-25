"""Cryptographically signed, externally verifiable JAMP verdicts."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class JampVerdict:
    """A verdict bound to an execution trace and its output digest."""

    trace_id: str
    status: str
    provider_model_id: str | None
    evidence_hash: str
    timestamp: float
    signature: str | None = None

    def _payload(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "provider_model_id": self.provider_model_id,
            "evidence_hash": self.evidence_hash,
            "timestamp": self.timestamp,
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
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> JampVerdict:
        """Parse only the public verdict contract; reject malformed payloads."""
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
        return cls(
            trace_id=trace_id,
            status=status,
            provider_model_id=provider_model_id,
            evidence_hash=evidence_hash,
            timestamp=float(timestamp),
            signature=signature,
        )
