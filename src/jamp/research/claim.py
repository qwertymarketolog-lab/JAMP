"""P20.4 deterministic hypothesis and claim verification.

Research-only module. Claims are content-addressed, immutable, and bound to
registry-backed P20 evidence. Logical status is derived only from explicit
rules and supplied premises/evidence; no I/O, runtime metadata, randomness,
or production-domain dependencies are permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .derivation import DerivedEvidence
from .registry import ArtifactRegistry

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_STATUSES = frozenset({"SUPPORTED", "REFUTED", "UNDETERMINED", "CONTRADICTED"})
_CLAIM_TYPES = frozenset({"HYPOTHESIS", "ASSERTION", "COMPARATIVE", "INFERENTIAL"})
_RUNTIME_KEYS = frozenset({"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"})


class ClaimError(ValueError):
    """Base P20.4 claim error."""


class ClaimIntegrityError(ClaimError):
    """Raised when claim, rule, evidence, or provenance integrity fails."""


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
    return value


def _hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise ClaimIntegrityError(f"{field} must be lowercase SHA-256")


def compute_claim_hash(claim_type: str, statement: str, premises: Sequence[Any], evidence_refs: Sequence[str], inference_rule: str, rule_version: str, result: Mapping[str, Any]) -> str:
    if claim_type not in _CLAIM_TYPES:
        raise ClaimError("invalid claim_type")
    if not isinstance(statement, str) or not statement.strip():
        raise ClaimError("statement must be non-empty")
    if not isinstance(inference_rule, str) or not inference_rule:
        raise ClaimError("inference_rule must be explicit")
    if not isinstance(rule_version, str) or not rule_version:
        raise ClaimError("rule_version must be explicit")
    refs = tuple(evidence_refs)
    for ref in refs:
        _hash(ref, "evidence_ref")
    material = {
        "claim_type": claim_type,
        "statement": " ".join(statement.split()),
        "premises": _thaw(_freeze(list(premises))),
        "evidence_refs": list(refs),
        "inference_rule": inference_rule,
        "rule_version": rule_version,
        "result": _thaw(_freeze(dict(result))),
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _verify_evidence(registry: ArtifactRegistry, ref: str | DerivedEvidence) -> tuple[str, Mapping[str, Any]]:
    if isinstance(ref, DerivedEvidence):
        try:
            ref.verify(registry)
        except Exception as exc:
            raise ClaimIntegrityError("derived evidence failed verification") from exc
        return ref.derived_evidence_hash, ref.provenance
    _hash(ref, "evidence_ref")
    try:
        artifact = registry.get(ref)
    except Exception as exc:
        raise ClaimIntegrityError("evidence reference is not registry-backed") from exc
    # Registry entries are P20.1 ResearchResult objects; verify by retrieving
    # their indexed provenance through the public integrity-checked accessor.
    try:
        entry = registry.index[ref]
        required = ("trace_hash", "initial_state_hash", "ordered_event_ids", "resulting_state_hash")
        if not all(k in entry for k in required):
            raise ClaimIntegrityError("complete evidence provenance required")
    except Exception as exc:
        if isinstance(exc, ClaimIntegrityError):
            raise
        raise ClaimIntegrityError("evidence provenance unavailable") from exc
    return artifact.result_hash, {
        "result_hash": artifact.result_hash,
        "trace_hash": artifact.trace_hash,
        "event_ids": tuple(entry["ordered_event_ids"]),
        "state_anchors": (entry["initial_state_hash"], entry["resulting_state_hash"]),
        "result_provenance": artifact.provenance,
    }


def evaluate_claim(*, evidence: Sequence[Any], premises: Sequence[Any], inference_rule: str) -> str:
    """Evaluate an explicit deterministic rule into one of four statuses."""
    if not isinstance(inference_rule, str) or not inference_rule:
        raise ClaimError("explicit inference_rule required")
    if not isinstance(premises, Sequence):
        raise ClaimError("premises must be a sequence")
    if inference_rule == "ALL_SUPPORT":
        if not premises:
            return "UNDETERMINED"
        values = [bool(x) for x in evidence]
        return "SUPPORTED" if len(values) >= len(premises) and all(values[:len(premises)]) else "UNDETERMINED"
    if inference_rule == "ANY_REFUTE":
        return "REFUTED" if any(bool(x) is False for x in evidence) else "UNDETERMINED"
    if inference_rule == "CONFLICT":
        values = {bool(x) for x in evidence}
        return "CONTRADICTED" if values == {True, False} else ("SUPPORTED" if values == {True} else "REFUTED" if values == {False} else "UNDETERMINED")
    if inference_rule == "DIRECT":
        if not evidence:
            return "UNDETERMINED"
        return "SUPPORTED" if bool(evidence[0]) else "REFUTED"
    raise ClaimError(f"unsupported inference_rule: {inference_rule!r}")


@dataclass(frozen=True, slots=True)
class Claim:
    claim_type: str
    statement: str
    premises: tuple[Any, ...]
    evidence_refs: tuple[str, ...]
    inference_rule: str
    rule_version: str
    result: Mapping[str, Any]
    provenance: Mapping[str, Any]
    status: str
    claim_hash: str

    def __post_init__(self) -> None:
        if self.claim_type not in _CLAIM_TYPES:
            raise ClaimIntegrityError("invalid claim_type")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ClaimIntegrityError("invalid statement")
        if not self.inference_rule or not self.rule_version:
            raise ClaimIntegrityError("rule and version are required")
        if self.status not in _STATUSES:
            raise ClaimIntegrityError("invalid status")
        for ref in self.evidence_refs:
            _hash(ref, "evidence_ref")
        object.__setattr__(self, "premises", tuple(_freeze(x) for x in self.premises))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "result", _freeze(dict(self.result)))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))
        expected = compute_claim_hash(self.claim_type, self.statement, self.premises, self.evidence_refs, self.inference_rule, self.rule_version, self.result)
        if expected != self.claim_hash:
            raise ClaimIntegrityError("claim_hash does not match content")

    def verify(self, registry: ArtifactRegistry, *, evidence_refs: Sequence[str] | None = None) -> bool:
        refs = tuple(self.evidence_refs if evidence_refs is None else evidence_refs)
        if refs != self.evidence_refs:
            raise ClaimIntegrityError("evidence substitution detected")
        proven = {}
        for ref in refs:
            key, prov = _verify_evidence(registry, ref)
            proven[key] = prov
        if set(proven) != set(refs):
            raise ClaimIntegrityError("evidence identity mismatch")
        expected = compute_claim_hash(self.claim_type, self.statement, self.premises, self.evidence_refs, self.inference_rule, self.rule_version, self.result)
        if expected != self.claim_hash:
            raise ClaimIntegrityError("claim integrity failure")
        if self.provenance.get("evidence") != proven:
            raise ClaimIntegrityError("provenance mismatch")
        return True

    def export(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "claim_type": self.claim_type,
            "statement": self.statement,
            "premises": _thaw(self.premises),
            "evidence_refs": self.evidence_refs,
            "inference_rule": self.inference_rule,
            "rule_version": self.rule_version,
            "result": _thaw(self.result),
            "provenance": _thaw(self.provenance),
            "status": self.status,
            "claim_hash": self.claim_hash,
        })


def verify_claim(registry: ArtifactRegistry, *, claim_type: str, statement: str, premises: Sequence[Any], evidence: Sequence[str | DerivedEvidence], inference_rule: str, rule_version: str, result: Mapping[str, Any], status: str | None = None) -> Claim:
    if not isinstance(registry, ArtifactRegistry):
        raise ClaimError("registry must be an ArtifactRegistry")
    if not isinstance(evidence, Sequence):
        raise ClaimError("evidence must be a sequence")
    frozen_premises = tuple(_freeze(x) for x in premises)
    if not frozen_premises and inference_rule not in {"DIRECT", "CONFLICT"}:
        raise ClaimIntegrityError("missing premise")
    if inference_rule not in {"ALL_SUPPORT", "ANY_REFUTE", "CONFLICT", "DIRECT"}:
        raise ClaimError("unsupported inference rule")
    refs: list[str] = []
    provenance: dict[str, Any] = {}
    truth_values: list[Any] = []
    for item in evidence:
        key, prov = _verify_evidence(registry, item)
        refs.append(key)
        provenance[key] = prov
        # Explicit result assertions are the only logical values accepted;
        # source payloads are evidence, not implicit truth assignments.
        if isinstance(item, DerivedEvidence):
            values = item.result.get("truth") if isinstance(item.result, Mapping) else None
            if values is not None:
                truth_values.extend(values if isinstance(values, (list, tuple)) else [values])
        else:
            artifact = registry.get(key)
            value = artifact.payload.get("truth") if isinstance(artifact.payload, Mapping) else None
            if value is not None:
                truth_values.append(value)
    if not truth_values and result.get("truth") is not None:
        tv = result.get("truth")
        truth_values.extend(tv if isinstance(tv, (list, tuple)) else [tv])
    computed_status = evaluate_claim(evidence=truth_values, premises=frozen_premises, inference_rule=inference_rule)
    final_status = computed_status if status is None else status
    if final_status not in _STATUSES:
        raise ClaimIntegrityError("invalid status")
    if final_status != computed_status:
        raise ClaimIntegrityError("status is not deterministically supported by evidence")
    ordered_refs = tuple(refs)
    claim_hash = compute_claim_hash(claim_type, statement, frozen_premises, ordered_refs, inference_rule, rule_version, result)
    return Claim(claim_type, " ".join(statement.split()), frozen_premises, ordered_refs, inference_rule, rule_version, result, {"evidence": provenance}, final_status, claim_hash)
