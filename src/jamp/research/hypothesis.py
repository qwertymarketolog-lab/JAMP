"""P20.5 immutable hypothesis lifecycle and refutation engine.

Research-only, deterministic, content-addressed, and isolated from production
JAMP domain, I/O, networking, and runtime metadata.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .claim import Claim
from .registry import ArtifactRegistry, RegistryIntegrityError

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = frozenset({"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"})
_HYPOTHESIS_TYPES = frozenset({"SCIENTIFIC", "CAUSAL", "COMPARATIVE", "PREDICTIVE", "EXPLANATORY"})
_TERMINAL = frozenset({"REFUTED", "REVISED", "RETIRED"})
_TRANSITIONS = {
    "ACTIVE": frozenset({"SUPPORTED", "REFUTED", "REVISED", "RETIRED"}),
    "SUPPORTED": frozenset({"REFUTED", "REVISED", "RETIRED"}),
    "REFUTED": frozenset(),
    "REVISED": frozenset(),
    "RETIRED": frozenset(),
}


class HypothesisError(ValueError):
    pass


class HypothesisIntegrityError(HypothesisError):
    pass


class HypothesisTransitionError(HypothesisError):
    pass


class HypothesisStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    REVISED = "REVISED"
    RETIRED = "RETIRED"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value):
            raise HypothesisIntegrityError("runtime metadata is forbidden")
        if any(not isinstance(k, str) for k in value):
            raise HypothesisIntegrityError("mapping keys must be strings")
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
        raise HypothesisIntegrityError(f"{field} must be lowercase SHA-256")


def _canonical_formulation(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HypothesisIntegrityError("formulation must be non-empty")
    return " ".join(value.split())


def compute_hypothesis_hash(
    formulation: str,
    hypothesis_type: str,
    source: Mapping[str, Any],
    parent_hypothesis_hash: str | None,
    claim_hashes: Sequence[str],
    evidence_hashes: Sequence[str],
    status: str | HypothesisStatus,
    transition_history: Sequence[Mapping[str, Any]],
) -> str:
    """Return the deterministic identity of a hypothesis record."""
    formulation = _canonical_formulation(formulation)
    if hypothesis_type not in _HYPOTHESIS_TYPES:
        raise HypothesisIntegrityError("invalid hypothesis_type")
    source_frozen = _freeze(source)
    if parent_hypothesis_hash is not None:
        _hash(parent_hypothesis_hash, "parent_hypothesis_hash")
    for ref in tuple(claim_hashes) + tuple(evidence_hashes):
        _hash(ref, "provenance hash")
    status_value = status.value if isinstance(status, HypothesisStatus) else status
    if status_value not in {s.value for s in HypothesisStatus}:
        raise HypothesisIntegrityError("invalid status")
    history = tuple(_freeze(x) for x in transition_history)
    material = {
        "formulation": formulation,
        "hypothesis_type": hypothesis_type,
        "source": _thaw(source_frozen),
        "parent_hypothesis_hash": parent_hypothesis_hash,
        "claim_hashes": list(dict.fromkeys(claim_hashes)),
        "evidence_hashes": list(dict.fromkeys(evidence_hashes)),
        "status": status_value,
        "transition_history": _thaw(history),
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _validate_transition_history(history: Sequence[Mapping[str, Any]], current: HypothesisStatus) -> tuple[Any, ...]:
    frozen = tuple(_freeze(x) for x in history)
    expected = HypothesisStatus.ACTIVE
    for transition in frozen:
        required = ("from_status", "to_status", "reason", "transition_hash")
        if not all(k in transition for k in required):
            raise HypothesisIntegrityError("incomplete transition record")
        try:
            source = HypothesisStatus(transition["from_status"])
            target = HypothesisStatus(transition["to_status"])
        except (ValueError, TypeError) as exc:
            raise HypothesisIntegrityError("invalid transition status") from exc
        if source != expected or target.value not in _TRANSITIONS[source.value]:
            raise HypothesisIntegrityError("invalid transition history")
        if not isinstance(transition["reason"], Mapping) or not transition["reason"]:
            raise HypothesisIntegrityError("transition reason is required")
        _validate_transition_reason(transition["reason"])
        _hash(transition["transition_hash"], "transition_hash")
        material = {k: _thaw(transition[k]) for k in ("from_status", "to_status", "reason")}
        expected_hash = hashlib.sha256(canonical_bytes(material)).hexdigest()
        if expected_hash != transition["transition_hash"]:
            raise HypothesisIntegrityError("transition hash mismatch")
        expected = target
    if expected != current:
        raise HypothesisIntegrityError("status/history mismatch")
    return frozen


def _validate_transition_reason(reason: Mapping[str, Any]) -> None:
    if not isinstance(reason, Mapping) or not reason:
        raise HypothesisTransitionError("transition reason is required")
    linked = False
    for key in ("claim_hash", "evidence_hash"):
        if key in reason:
            _hash(reason[key], key)
            linked = True
    if not linked:
        raise HypothesisTransitionError("transition reason must link a claim_hash or evidence_hash")


def compute_transition_hash(from_status: str | HypothesisStatus, to_status: str | HypothesisStatus, reason: Mapping[str, Any]) -> str:
    source = from_status.value if isinstance(from_status, HypothesisStatus) else from_status
    target = to_status.value if isinstance(to_status, HypothesisStatus) else to_status
    if source not in _TRANSITIONS or target not in _TRANSITIONS[source]:
        raise HypothesisTransitionError("illegal hypothesis transition")
    _validate_transition_reason(reason)
    frozen = _freeze(reason)
    return hashlib.sha256(canonical_bytes({"from_status": source, "to_status": target, "reason": _thaw(frozen)})).hexdigest()


@dataclass(frozen=True, slots=True)
class HypothesisRecord:
    formulation: str
    hypothesis_type: str
    source: Mapping[str, Any]
    parent_hypothesis_hash: str | None
    claim_hashes: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    status: HypothesisStatus
    transition_history: tuple[Mapping[str, Any], ...]
    hypothesis_hash: str

    def __post_init__(self) -> None:
        formulation = _canonical_formulation(self.formulation)
        if self.hypothesis_type not in _HYPOTHESIS_TYPES:
            raise HypothesisIntegrityError("invalid hypothesis_type")
        source = _freeze(self.source)
        if self.parent_hypothesis_hash is not None:
            _hash(self.parent_hypothesis_hash, "parent_hypothesis_hash")
        claims = tuple(dict.fromkeys(self.claim_hashes))
        evidence = tuple(dict.fromkeys(self.evidence_hashes))
        for ref in claims + evidence:
            _hash(ref, "provenance hash")
        try:
            status = self.status if isinstance(self.status, HypothesisStatus) else HypothesisStatus(self.status)
        except (ValueError, TypeError) as exc:
            raise HypothesisIntegrityError("invalid status") from exc
        try:
            history = _validate_transition_history(self.transition_history, status)
        except HypothesisTransitionError as exc:
            raise HypothesisIntegrityError(str(exc)) from exc
        object.__setattr__(self, "formulation", formulation)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "claim_hashes", claims)
        object.__setattr__(self, "evidence_hashes", evidence)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "transition_history", history)
        expected = compute_hypothesis_hash(formulation, self.hypothesis_type, source, self.parent_hypothesis_hash, claims, evidence, status, history)
        if expected != self.hypothesis_hash:
            raise HypothesisIntegrityError("hypothesis_hash does not match content")

    @property
    def hypothesis_id(self) -> str:
        return self.hypothesis_hash

    @property
    def is_terminal(self) -> bool:
        return self.status.value in _TERMINAL

    def verify(self, registry: ArtifactRegistry | None = None, *, parent: "HypothesisRecord | None" = None, claims: Sequence[Claim] | None = None) -> bool:
        if self.parent_hypothesis_hash is None:
            if parent is not None:
                raise HypothesisIntegrityError("root hypothesis cannot have a parent object")
        else:
            _hash(self.parent_hypothesis_hash, "parent_hypothesis_hash")
            if parent is None or parent.hypothesis_hash != self.parent_hypothesis_hash:
                raise HypothesisIntegrityError("parent hypothesis integrity failure")
            if parent.status not in {HypothesisStatus.REFUTED, HypothesisStatus.REVISED}:
                raise HypothesisIntegrityError("descendant requires a refuted or revised parent")
        if self.evidence_hashes:
            if registry is None:
                raise HypothesisIntegrityError("registry is required for evidence verification")
            for evidence_hash in self.evidence_hashes:
                try:
                    registry.verify(evidence_hash)
                    entry = registry.index[evidence_hash]
                    if entry.get("trace_hash") != registry.get(evidence_hash).trace_hash:
                        raise HypothesisIntegrityError("evidence provenance index mismatch")
                except (KeyError, RegistryIntegrityError, Exception) as exc:
                    if isinstance(exc, HypothesisIntegrityError):
                        raise
                    raise HypothesisIntegrityError("evidence is not registry-backed or is tampered") from exc
        if claims is not None:
            supplied = tuple(dict.fromkeys(c.claim_hash for c in claims))
            if supplied != self.claim_hashes:
                raise HypothesisIntegrityError("claim substitution detected")
            for claim in claims:
                if registry is None:
                    raise HypothesisIntegrityError("registry is required for claim verification")
                try:
                    claim.verify(registry)
                except Exception as exc:
                    raise HypothesisIntegrityError("claim integrity verification failed") from exc
        expected = compute_hypothesis_hash(self.formulation, self.hypothesis_type, self.source, self.parent_hypothesis_hash, self.claim_hashes, self.evidence_hashes, self.status, self.transition_history)
        if expected != self.hypothesis_hash:
            raise HypothesisIntegrityError("hypothesis integrity failure")
        return True

    def export(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_hash": self.hypothesis_hash,
            "formulation": self.formulation,
            "hypothesis_type": self.hypothesis_type,
            "source": _thaw(self.source),
            "parent_hypothesis_hash": self.parent_hypothesis_hash,
            "claim_hashes": self.claim_hashes,
            "evidence_hashes": self.evidence_hashes,
            "status": self.status.value,
            "transition_history": _thaw(self.transition_history),
        })


def make_hypothesis(
    *, formulation: str, hypothesis_type: str, source: Mapping[str, Any],
    parent: HypothesisRecord | None = None,
    claim_hashes: Sequence[str] = (), evidence_hashes: Sequence[str] = (),
) -> HypothesisRecord:
    parent_hash = parent.hypothesis_hash if parent is not None else None
    if parent is not None and parent.status not in {HypothesisStatus.REFUTED, HypothesisStatus.REVISED}:
        raise HypothesisTransitionError("descendant requires a refuted or revised parent")
    history: tuple[Mapping[str, Any], ...] = ()
    return HypothesisRecord(formulation, hypothesis_type, source, parent_hash, tuple(dict.fromkeys(claim_hashes)), tuple(dict.fromkeys(evidence_hashes)), HypothesisStatus.ACTIVE, history, compute_hypothesis_hash(formulation, hypothesis_type, source, parent_hash, claim_hashes, evidence_hashes, HypothesisStatus.ACTIVE, history))


def transition_hypothesis(hypothesis: HypothesisRecord, to_status: HypothesisStatus | str, reason: Mapping[str, Any], *, claims: Sequence[str] = (), evidence: Sequence[str] = ()) -> HypothesisRecord:
    try:
        target = to_status if isinstance(to_status, HypothesisStatus) else HypothesisStatus(to_status)
    except (ValueError, TypeError) as exc:
        raise HypothesisTransitionError("invalid target status") from exc
    if target.value not in _TRANSITIONS[hypothesis.status.value]:
        raise HypothesisTransitionError(f"illegal transition {hypothesis.status.value} -> {target.value}")
    _validate_transition_reason(reason)
    reason_frozen = _freeze(reason)
    transition_hash = compute_transition_hash(hypothesis.status, target, reason)
    transition = MappingProxyType({"from_status": hypothesis.status.value, "to_status": target.value, "reason": reason_frozen, "transition_hash": transition_hash})
    history = hypothesis.transition_history + (transition,)
    claim_refs = tuple(dict.fromkeys(hypothesis.claim_hashes + tuple(claims)))
    evidence_refs = tuple(dict.fromkeys(hypothesis.evidence_hashes + tuple(evidence)))
    for ref in claim_refs + evidence_refs:
        _hash(ref, "provenance hash")
    new_hash = compute_hypothesis_hash(hypothesis.formulation, hypothesis.hypothesis_type, hypothesis.source, hypothesis.parent_hypothesis_hash, claim_refs, evidence_refs, target, history)
    return HypothesisRecord(hypothesis.formulation, hypothesis.hypothesis_type, hypothesis.source, hypothesis.parent_hypothesis_hash, claim_refs, evidence_refs, target, history, new_hash)
