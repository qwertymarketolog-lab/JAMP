"""P20.10 deterministic claim synthesis and consensus resolution.

Research-only, content-addressed, immutable, and epistemically bounded.
Interpretations are evidence-bearing inputs; consensus is a structured
resolution state, never an assertion of absolute truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes

_HASH = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN = frozenset({"timestamp", "uuid", "pid", "process_id", "hostname", "memory_address", "environment", "local_path"})


class ConsensusIntegrityError(ValueError):
    """Raised when claim, interpretation, consensus, or provenance integrity fails."""


class ConsensusStatus(str, Enum):
    CONSENSUS = "CONSENSUS"
    CONTESTED = "CONTESTED"
    UNDETERMINED = "UNDETERMINED"


class EpistemicStatus(str, Enum):
    FALSIFIABLE = "FALSIFIABLE"


def _check(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN:
                raise ConsensusIntegrityError(f"runtime metadata forbidden: {key}")
            if not isinstance(key, str):
                raise ConsensusIntegrityError("mapping keys must be strings")
            _check(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check(item)


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(x) for x in value]
    return value


def _freeze(value: Any) -> Any:
    _check(value)
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(x) for x in value)
    return value


def _sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(_plain(value))).hexdigest()


def _hash_id(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ConsensusIntegrityError(f"{field} must be lowercase SHA-256")


def _classification(item: Any) -> str:
    value = getattr(item, "classification", None)
    value = getattr(value, "value", value)
    if value not in {"SUPPORTS", "REFUTES", "UNDETERMINED"}:
        raise ConsensusIntegrityError("invalid interpretation classification")
    return value


def compute_consensus_hash(payload: Mapping[str, Any]) -> str:
    """Hash canonical consensus semantics, excluding no material fields."""
    return _sha(payload)


def compute_claim_hash(payload: Mapping[str, Any]) -> str:
    """Hash canonical claim semantics including its consensus resolution."""
    return _sha(payload)


@dataclass(frozen=True, slots=True)
class ConsensusRecord:
    consensus_hash: str
    status: ConsensusStatus
    supporting_hashes: tuple[str, ...]
    conflicting_hashes: tuple[str, ...]
    dissenting_hashes: tuple[str, ...]

    def canonical_payload(self) -> Mapping[str, Any]:
        return {"status": self.status.value, "supporting_hashes": list(self.supporting_hashes), "conflicting_hashes": list(self.conflicting_hashes), "dissenting_hashes": list(self.dissenting_hashes)}

    def verify(self) -> bool:
        _hash_id(self.consensus_hash, "consensus_hash")
        if compute_consensus_hash(self.canonical_payload()) != self.consensus_hash:
            raise ConsensusIntegrityError("consensus hash mismatch")
        if self.status == ConsensusStatus.CONSENSUS and self.conflicting_hashes:
            raise ConsensusIntegrityError("false consensus")
        return True


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    claim_hash: str
    statement: str
    interpretation_hashes: tuple[str, ...]
    target: str
    method: str
    parameters: Any
    consensus: ConsensusRecord
    provenance: Mapping[str, Any]
    epistemic_status: EpistemicStatus = EpistemicStatus.FALSIFIABLE
    falsifiable: bool = True

    @property
    def supporting_hashes(self): return self.consensus.supporting_hashes
    @property
    def conflicting_hashes(self): return self.consensus.conflicting_hashes
    @property
    def execution_hashes(self): return tuple(self.provenance["execution_hashes"])
    @property
    def plan_hashes(self): return tuple(self.provenance["plan_hashes"])
    @property
    def question_hashes(self): return tuple(self.provenance["question_hashes"])
    @property
    def trace_hashes(self): return tuple(self.provenance["trace_hashes"])
    @property
    def state_hashes(self): return tuple(self.provenance["state_hashes"])

    def canonical_payload(self) -> Mapping[str, Any]:
        return {"statement": self.statement, "interpretation_hashes": list(self.interpretation_hashes), "target": self.target, "method": self.method, "parameters": _plain(self.parameters), "consensus": _plain(self.consensus.canonical_payload()), "provenance": _plain(self.provenance), "epistemic_status": self.epistemic_status.value, "falsifiable": self.falsifiable}

    def provenance_chain(self) -> tuple[str, ...]:
        return tuple(self.provenance["question_hashes"] + self.provenance["plan_hashes"] + self.provenance["execution_hashes"] + self.interpretation_hashes)

    def verify(self, registry: Mapping[str, Any]) -> bool:
        for h in self.interpretation_hashes:
            _hash_id(h, "interpretation_hash")
            item = registry.get(h)
            if item is None:
                raise ConsensusIntegrityError("unknown interpretation_hash")
            verifier = getattr(item, "verify", None)
            if callable(verifier) and not verifier(registry) and not verifier():
                raise ConsensusIntegrityError("interpretation integrity failed")
            if getattr(item, "interpretation_hash", h) != h:
                raise ConsensusIntegrityError("interpretation substitution detected")
        self.consensus.verify()
        if compute_claim_hash(self.canonical_payload()) != self.claim_hash:
            raise ConsensusIntegrityError("claim hash mismatch")
        _check(self.canonical_payload())
        return True

    def export(self) -> Mapping[str, Any]:
        self.verify({h: _NullRegistryItem(h) for h in self.interpretation_hashes}) if False else None
        return MappingProxyType({"claim_hash": self.claim_hash, **_plain(self.canonical_payload())})


class _NullRegistryItem:
    def __init__(self, h): self.interpretation_hash = h


def _resolve(items: Sequence[Any]) -> ConsensusRecord:
    hashes = tuple(sorted(getattr(x, "interpretation_hash") for x in items))
    support = tuple(sorted(h for h, x in ((getattr(i, "interpretation_hash"), i) for i in items) if _classification(x) == "SUPPORTS"))
    conflict = tuple(sorted(h for h, x in ((getattr(i, "interpretation_hash"), i) for i in items) if _classification(x) == "REFUTES"))
    unknown = tuple(sorted(h for h, x in ((getattr(i, "interpretation_hash"), i) for i in items) if _classification(x) == "UNDETERMINED"))
    if not support and not conflict:
        status = ConsensusStatus.UNDETERMINED
    elif support and conflict:
        status = ConsensusStatus.CONTESTED
    elif support and not unknown:
        status = ConsensusStatus.CONSENSUS
    else:
        status = ConsensusStatus.UNDETERMINED
    dissent = tuple(sorted(conflict + unknown))
    payload = {"status": status.value, "supporting_hashes": list(support), "conflicting_hashes": list(conflict), "dissenting_hashes": list(dissent)}
    return ConsensusRecord(_sha(payload), status, support, conflict, dissent)


def make_claim(registry: Mapping[str, Any], *, statement: str, interpretations: Sequence[Any], method: str, parameters: Mapping[str, Any], target: str | None = None, consensus_status: str | None = None) -> ClaimRecord:
    if not isinstance(statement, str) or not statement.strip() or not isinstance(method, str) or not method.strip():
        raise ConsensusIntegrityError("statement and method are required")
    if not interpretations:
        raise ConsensusIntegrityError("at least one verified interpretation is required")
    _check(parameters)
    ordered = tuple(sorted(interpretations, key=lambda x: getattr(x, "interpretation_hash", "")))
    for item in ordered:
        h = getattr(item, "interpretation_hash", None)
        _hash_id(h, "interpretation_hash")
        registered = registry.get(h)
        if registered is None or registered is not item:
            raise ConsensusIntegrityError("interpretation must be registry-backed")
        verifier = getattr(item, "verify", None)
        if callable(verifier):
            try: ok = verifier(registry)
            except TypeError: ok = verifier()
            if ok is not True: raise ConsensusIntegrityError("interpretation integrity failed")
    consensus = _resolve(ordered)
    if consensus_status is not None and consensus_status != consensus.status.value:
        raise ConsensusIntegrityError("manufactured consensus status")
    target = target or str(getattr(ordered[0], "analytical_target", ""))
    if not target.strip(): raise ConsensusIntegrityError("target is required")
    provenance = {
        "interpretation_hashes": [getattr(x, "interpretation_hash") for x in ordered],
        "result_hashes": sorted(getattr(x, "result_hash") for x in ordered),
        "execution_hashes": sorted(getattr(x, "execution_hash") for x in ordered),
        "plan_hashes": sorted(getattr(x, "plan_hash") for x in ordered),
        "question_hashes": sorted(getattr(x, "question_hash") for x in ordered),
        "trace_hashes": sorted(getattr(x, "trace_hash") for x in ordered),
        "state_hashes": sorted(getattr(x, "state_hash") for x in ordered),
    }
    payload = {"statement": " ".join(statement.split()), "interpretation_hashes": [getattr(x, "interpretation_hash") for x in ordered], "target": target, "method": method.strip(), "parameters": _plain(parameters), "consensus": _plain(consensus.canonical_payload()), "provenance": provenance, "epistemic_status": EpistemicStatus.FALSIFIABLE.value, "falsifiable": True}
    claim_hash = compute_claim_hash(payload)
    record = ClaimRecord(claim_hash, payload["statement"], tuple(payload["interpretation_hashes"]), target, method.strip(), _freeze(parameters), consensus, _freeze(provenance), EpistemicStatus.FALSIFIABLE, True)
    if not record.verify(registry): raise ConsensusIntegrityError("claim self-verification failed")
    return record
