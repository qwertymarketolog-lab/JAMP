"""P20.4 deterministic hypothesis and claim verification.

Research-only module. Claims are content-addressed, immutable, and bound to
registry-backed P20 evidence. No I/O, runtime metadata, randomness, or
production-domain dependencies are permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .derivation import DerivedEvidence, compute_derived_evidence_hash
from .registry import ArtifactRegistry

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = frozenset({"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"})
_CLAIM_TYPES = frozenset({"HYPOTHESIS", "ASSERTION", "COMPARATIVE", "INFERENTIAL"})
_RULES = frozenset({"EVIDENCE_STATUS", "PREMISE_CONJUNCTION"})


class ClaimError(ValueError):
    """Base P20.4 claim error."""


class ClaimIntegrityError(ClaimError):
    """Raised when claim, evidence, premise, or provenance integrity fails."""


class ClaimRuleError(ClaimError):
    """Raised for missing, unknown, or unsupported inference rules."""


class ClaimStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    UNDETERMINED = "UNDETERMINED"
    CONTRADICTED = "CONTRADICTED"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value):
            raise ClaimIntegrityError("runtime metadata is forbidden")
        if any(not isinstance(k, str) for k in value):
            raise ClaimIntegrityError("mapping keys must be strings")
        return MappingProxyType({k: _freeze(value[k]) for k in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze(x) for x in value)
    if isinstance(value, tuple):
        return tuple(_freeze(x) for x in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ClaimIntegrityError(f"{field} must be lowercase SHA-256")


def _canonical_statement(statement: str) -> str:
    if not isinstance(statement, str) or not statement.strip():
        raise ClaimIntegrityError("statement must be non-empty")
    return " ".join(statement.split())


def _validate_premises(premises: Sequence[Any]) -> tuple[Any, ...]:
    frozen = tuple(_freeze(x) for x in premises)
    valid = {s.value for s in ClaimStatus}
    for premise in frozen:
        if isinstance(premise, Mapping) and "status" in premise and premise["status"] not in valid:
            raise ClaimIntegrityError("invalid premise status")
    return frozen


def compute_claim_hash(claim_type: str, statement: str, premises: Sequence[Any], evidence_refs: Sequence[str], inference_rule: str, rule_version: str, status: str | ClaimStatus) -> str:
    """Compute content-addressed identity over canonical claim semantics."""
    if claim_type not in _CLAIM_TYPES:
        raise ClaimIntegrityError("invalid claim_type")
    statement = _canonical_statement(statement)
    if not inference_rule:
        raise ClaimRuleError("inference_rule must be explicit")
    if not rule_version:
        raise ClaimRuleError("rule_version must be explicit")
    status_value = status.value if isinstance(status, ClaimStatus) else status
    if status_value not in {s.value for s in ClaimStatus}:
        raise ClaimIntegrityError("invalid status")
    refs = tuple(dict.fromkeys(evidence_refs))
    for ref in refs:
        _hash(ref, "evidence_ref")
    material = {
        "claim_type": claim_type,
        "statement": statement,
        "premises": _thaw(_validate_premises(premises)),
        "evidence_refs": list(refs),
        "inference_rule": inference_rule,
        "rule_version": rule_version,
        "status": status_value,
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _verify_derived_evidence(registry: ArtifactRegistry, evidence: DerivedEvidence) -> tuple[str, Mapping[str, Any]]:
    expected_hash = compute_derived_evidence_hash(
        evidence.source_hashes, evidence.analysis_type, evidence.algorithm_version,
        evidence.parameters, evidence.result,
    )
    if expected_hash != evidence.derived_evidence_hash:
        raise ClaimIntegrityError("derived evidence hash mismatch")
    sources = evidence.provenance.get("sources")
    if not isinstance(sources, Mapping):
        raise ClaimIntegrityError("recursive source provenance is required")
    if set(sources) != set(evidence.source_hashes):
        raise ClaimIntegrityError("derived evidence source substitution detected")
    for source_hash in evidence.source_hashes:
        source = sources[source_hash]
        if not isinstance(source, Mapping):
            raise ClaimIntegrityError("invalid source provenance")
        if "result_hash" in source:
            _verify_evidence(registry, source["result_hash"])
        if "leaves" in source:
            for leaf in source["leaves"]:
                if not isinstance(leaf, Mapping):
                    raise ClaimIntegrityError("invalid recursive provenance leaf")
                for field in ("result_hash", "trace_hash"):
                    _hash(leaf[field], field)
                for field in ("event_ids", "state_anchors"):
                    if field not in leaf:
                        raise ClaimIntegrityError("incomplete recursive provenance")
    return evidence.derived_evidence_hash, evidence.provenance


def _verify_evidence(registry: ArtifactRegistry, ref: str | DerivedEvidence) -> tuple[str, Mapping[str, Any]]:
    if isinstance(ref, DerivedEvidence):
        return _verify_derived_evidence(registry, ref)
    _hash(ref, "evidence_ref")
    try:
        artifact = registry.get(ref)
        entry = registry.index[ref]
        required = ("trace_hash", "initial_state_hash", "ordered_event_ids", "resulting_state_hash")
        if not all(k in entry for k in required):
            raise ClaimIntegrityError("complete evidence provenance required")
        if not artifact.verify_integrity():
            raise ClaimIntegrityError("registered evidence integrity failure")
    except ClaimIntegrityError:
        raise
    except Exception as exc:
        raise ClaimIntegrityError("evidence reference is not registry-backed") from exc
    return artifact.result_hash, {
        "result_hash": artifact.result_hash,
        "trace_hash": artifact.trace_hash,
        "event_ids": tuple(entry["ordered_event_ids"]),
        "state_anchors": (entry["initial_state_hash"], entry["resulting_state_hash"]),
        "result_provenance": artifact.provenance,
    }


def _polarity(item: DerivedEvidence) -> str | None:
    value = item.result.get("polarity")
    return value if value in {s.value for s in ClaimStatus} else None


def evaluate_claim(evidence: Sequence[DerivedEvidence], premises: Sequence[Any], inference_rule: str) -> ClaimStatus:
    """Evaluate explicit evidence deterministically; this function is pure."""
    if not inference_rule:
        raise ClaimRuleError("inference_rule must be explicit")
    if inference_rule not in _RULES:
        raise ClaimRuleError(f"unsupported inference_rule: {inference_rule!r}")
    premises_frozen = _validate_premises(premises)
    if inference_rule == "PREMISE_CONJUNCTION":
        if not premises_frozen:
            raise ClaimIntegrityError("missing premise")
        statuses = [p.get("status") for p in premises_frozen if isinstance(p, Mapping)]
        return ClaimStatus.SUPPORTED if statuses and all(s == ClaimStatus.SUPPORTED.value for s in statuses) else ClaimStatus.UNDETERMINED
    polarities = [_polarity(item) for item in evidence]
    polarities = [p for p in polarities if p is not None]
    if not polarities:
        return ClaimStatus.UNDETERMINED
    values = set(polarities)
    if "SUPPORTED" in values and "REFUTED" in values:
        return ClaimStatus.CONTRADICTED
    if "SUPPORTED" in values:
        return ClaimStatus.SUPPORTED
    if "REFUTED" in values:
        return ClaimStatus.REFUTED
    return ClaimStatus.UNDETERMINED


@dataclass(frozen=True, slots=True)
class Claim:
    claim_type: str
    statement: str
    premises: tuple[Any, ...]
    evidence_refs: tuple[str, ...]
    inference_rule: str
    rule_version: str
    status: ClaimStatus
    provenance: Mapping[str, Any]
    claim_hash: str

    def __post_init__(self) -> None:
        if self.claim_type not in _CLAIM_TYPES:
            raise ClaimIntegrityError("invalid claim_type")
        statement = _canonical_statement(self.statement)
        premises = _validate_premises(self.premises)
        refs = tuple(dict.fromkeys(self.evidence_refs))
        for ref in refs:
            _hash(ref, "evidence_ref")
        if not self.inference_rule or not self.rule_version:
            raise ClaimRuleError("rule and version are required")
        status = self.status if isinstance(self.status, ClaimStatus) else ClaimStatus(self.status)
        provenance = _freeze(dict(self.provenance))
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "premises", premises)
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "provenance", provenance)
        expected = compute_claim_hash(self.claim_type, statement, premises, refs, self.inference_rule, self.rule_version, status)
        if expected != self.claim_hash:
            raise ClaimIntegrityError("claim_hash does not match content")

    def verify(self, registry: ArtifactRegistry, *, evidence: Sequence[str | DerivedEvidence] | None = None, inference_rule: str | None = None) -> bool:
        if evidence is not None:
            supplied = tuple(_verify_evidence(registry, item)[0] for item in evidence)
            if tuple(dict.fromkeys(supplied)) != self.evidence_refs:
                raise ClaimIntegrityError("evidence substitution detected")
        if inference_rule is not None and inference_rule != self.inference_rule:
            raise ClaimIntegrityError("inference rule substitution detected")
        proven = {key: prov for key, prov in (_verify_evidence(registry, ref) for ref in self.evidence_refs)}
        if self.provenance.get("evidence") != proven:
            raise ClaimIntegrityError("provenance mismatch")
        expected = compute_claim_hash(self.claim_type, self.statement, self.premises, self.evidence_refs, self.inference_rule, self.rule_version, self.status)
        if expected != self.claim_hash:
            raise ClaimIntegrityError("claim integrity failure")
        return True

    def export(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "claim_type": self.claim_type,
            "statement": self.statement,
            "premises": _thaw(self.premises),
            "evidence_refs": self.evidence_refs,
            "inference_rule": self.inference_rule,
            "rule_version": self.rule_version,
            "status": self.status.value,
            "provenance": _thaw(self.provenance),
            "claim_hash": self.claim_hash,
        })


def make_claim(registry: ArtifactRegistry, *, statement: str, claim_type: str, premises: Sequence[Any], evidence: Sequence[str | DerivedEvidence], inference_rule: str, rule_version: str, status: ClaimStatus | str) -> Claim:
    if not inference_rule:
        raise ClaimRuleError("inference_rule must be explicit")
    if inference_rule not in _RULES:
        raise ClaimRuleError(f"unsupported inference_rule: {inference_rule!r}")
    if not rule_version:
        raise ClaimRuleError("rule_version must be explicit")
    premises_frozen = _validate_premises(premises)
    if inference_rule == "PREMISE_CONJUNCTION" and not premises_frozen:
        raise ClaimIntegrityError("missing premise")
    verified: list[DerivedEvidence] = []
    refs: list[str] = []
    provenance: dict[str, Any] = {}
    for item in evidence:
        key, prov = _verify_evidence(registry, item)
        refs.append(key)
        provenance[key] = prov
        if not isinstance(item, DerivedEvidence):
            raise ClaimIntegrityError("claims must bind verified DerivedEvidence objects")
        verified.append(item)
    refs = list(dict.fromkeys(refs))
    computed = evaluate_claim(tuple(verified), premises_frozen, inference_rule)
    expected_status = status if isinstance(status, ClaimStatus) else ClaimStatus(status)
    if expected_status != computed:
        raise ClaimIntegrityError("status is not deterministically supported by evidence")
    claim_hash = compute_claim_hash(claim_type, statement, premises_frozen, tuple(refs), inference_rule, rule_version, expected_status)
    return Claim(claim_type, _canonical_statement(statement), premises_frozen, tuple(refs), inference_rule, rule_version, expected_status, {"evidence": provenance}, claim_hash)
