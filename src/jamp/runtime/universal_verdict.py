"""Isolated Universal Verdict v0 data contract and hashing helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, replace
from typing import Any

from jamp.runtime.verdict import JampVerdict

_ALLOWED_RESULTS = frozenset({"VERIFIED", "CONTRADICTED", "INCONCLUSIVE", "PARTIAL"})


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize a payload using the single normative v0 canonicalization."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256_hash(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def compute_jamp_verdict_hash(jv: JampVerdict) -> str:
    """Hash the unchanged JampVerdict payload with its signing canonicalization."""
    payload = jv._payload()
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class SpecRef:
    spec_id: str
    spec_hash: str


@dataclass(frozen=True)
class CriteriaRef:
    criteria_id: str
    criteria_hash: str


@dataclass(frozen=True)
class ExecutionRef:
    jamp_verdict_hash: str
    execution_status: str


@dataclass(frozen=True)
class EvidenceRef:
    type: str
    ref_hash: str
    source_sha256: str


@dataclass(frozen=True)
class UniversalClassification:
    label: str
    classification_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "classification_hash", _sha256_hash({"label": self.label})
        )


@dataclass(frozen=True)
class VerdictResult:
    result: str
    verdict_hash: str = ""

    def __post_init__(self) -> None:
        if self.result not in _ALLOWED_RESULTS:
            raise ValueError(f"Unsupported v0 verdict result: {self.result}")


@dataclass(frozen=True)
class VerifierInfo:
    version: str
    reproducible: bool
    aggregation_rule_hash: str


@dataclass(frozen=True)
class UniversalVerdict:
    spec_ref: SpecRef
    criteria_ref: CriteriaRef
    execution_ref: ExecutionRef
    evidence_refs: tuple[EvidenceRef, ...]
    classification: UniversalClassification
    verdict: VerdictResult
    verifier: VerifierInfo
    timestamp: str

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_refs, tuple):
            raise TypeError("evidence_refs must be a tuple")
        if not isinstance(self.verifier.reproducible, bool):
            raise TypeError("reproducible must be a bool")
        object.__setattr__(
            self,
            "verdict",
            replace(self.verdict, verdict_hash=self.compute_verdict_hash()),
        )

    def canonical_payload(self) -> dict[str, Any]:
        """Return the complete hash-covered payload, excluding verdict_hash."""
        return {
            "spec_ref": asdict(self.spec_ref),
            "criteria_ref": asdict(self.criteria_ref),
            "execution_ref": asdict(self.execution_ref),
            "evidence_refs": [asdict(item) for item in self.evidence_refs],
            "classification": asdict(self.classification),
            "verdict": {"result": self.verdict.result},
            "verifier": asdict(self.verifier),
            "timestamp": self.timestamp,
        }

    def compute_verdict_hash(self) -> str:
        """Compute the canonical v0 hash without verdict_hash or signature."""
        return _sha256_hash(self.canonical_payload())

    def sign(self, secret: bytes) -> str:
        """Return HMAC-SHA256 over the explicit verdict hash."""
        if not secret:
            raise ValueError("Signing secret must not be empty")
        return hmac.new(
            secret, self.verdict.verdict_hash.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verify(self, secret: bytes, sig: str) -> bool:
        """Verify HMAC without treating signature validity as truth verification."""
        if not secret or not isinstance(sig, str):
            return False
        return hmac.compare_digest(self.sign(secret), sig)

    def is_confirmed(self) -> bool:
        """Only reproducible VERIFIED or CONTRADICTED outcomes are confirmed."""
        return self.verifier.reproducible and self.verdict.result in {
            "VERIFIED",
            "CONTRADICTED",
        }
