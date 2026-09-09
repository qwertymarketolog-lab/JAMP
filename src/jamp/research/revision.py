"""P20.11 deterministic research-loop closure and hypothesis revision."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_bytes
from .hypothesis import HypothesisRecord, HypothesisStatus

_HASH = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN = frozenset({"timestamp", "uuid", "pid", "process_id", "hostname", "memory_address", "environment", "local_path"})
_STATUSES = frozenset({"CONSENSUS", "CONTESTED", "UNDETERMINED"})
_TYPES = frozenset({"REFINEMENT", "REVISION", "ALTERNATIVE", "GENERALIZATION", "RESTRICTION"})
_EPISTEMIC = frozenset({"FALSIFIABLE", "PROVISIONAL", "OPEN"})

class RevisionIntegrityError(ValueError):
    pass

class RevisionStatus(str, Enum):
    CONSENSUS = "CONSENSUS"
    CONTESTED = "CONTESTED"
    UNDETERMINED = "UNDETERMINED"

def _check(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str): raise RevisionIntegrityError("mapping keys must be strings")
            if key.lower() in _FORBIDDEN: raise RevisionIntegrityError(f"runtime metadata forbidden: {key}")
            _check(item)
    elif isinstance(value, (list, tuple)):
        for item in value: _check(item)

def _plain(value: Any) -> Any:
    if isinstance(value, Enum): return value.value
    if isinstance(value, Mapping): return {str(k): _plain(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    return value

def _freeze(value: Any) -> Any:
    _check(value)
    if isinstance(value, Mapping): return MappingProxyType({k: _freeze(v) for k, v in sorted(value.items())})
    if isinstance(value, (list, tuple)): return tuple(_freeze(v) for v in value)
    return value

def _hash_id(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _HASH.fullmatch(value): raise RevisionIntegrityError(f"{field} must be lowercase SHA-256")

def _status(trigger: Any) -> RevisionStatus:
    raw = getattr(getattr(trigger, "status", None), "value", getattr(trigger, "status", None))
    if raw not in _STATUSES: raise RevisionIntegrityError("trigger must expose a valid consensus status")
    return RevisionStatus(raw)

def _upstream(trigger: Any) -> tuple[str, ...]:
    fn = getattr(trigger, "provenance_chain", None)
    if callable(fn): chain = tuple(x for x in fn() if x is not None)
    else: chain = tuple((getattr(trigger, "provenance", {}) or {}).get("upstream_chain", ()))
    for item in chain: _hash_id(item, "upstream provenance hash")
    return chain

def compute_revision_hash(payload: Mapping[str, Any]) -> str:
    _check(payload)
    return hashlib.sha256(canonical_bytes(_plain(payload))).hexdigest()

@dataclass(frozen=True, slots=True)
class RevisionRecord:
    revision_hash: str
    parent_hypothesis_hash: str
    trigger_consensus_hash: str
    trigger_status: RevisionStatus
    formulation: str
    revision_type: str
    revision_method: str
    parameters: Mapping[str, Any]
    epistemic_status: str
    rationale: Mapping[str, Any]
    provenance: Mapping[str, Any]
    loop_closure: Mapping[str, Any]
    lineage: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {"parent_hypothesis_hash": self.parent_hypothesis_hash, "trigger_consensus_hash": self.trigger_consensus_hash, "trigger_status": self.trigger_status.value, "formulation": self.formulation, "revision_type": self.revision_type, "revision_method": self.revision_method, "parameters": _plain(self.parameters), "epistemic_status": self.epistemic_status, "rationale": _plain(self.rationale), "provenance": _plain(self.provenance), "loop_closure": _plain(self.loop_closure)}

    def verify(self, registry: Mapping[str, Any] | None = None, *, parent_hypothesis: HypothesisRecord | None = None) -> bool:
        _hash_id(self.revision_hash, "revision_hash"); _hash_id(self.parent_hypothesis_hash, "parent_hypothesis_hash"); _hash_id(self.trigger_consensus_hash, "trigger_consensus_hash")
        if self.trigger_status.value not in _STATUSES or self.revision_type not in _TYPES or self.epistemic_status not in _EPISTEMIC: raise RevisionIntegrityError("invalid revision enum value")
        if not self.formulation.strip() or not self.revision_method.strip() or not self.rationale: raise RevisionIntegrityError("revision formulation, method, and rationale are required")
        _check(self.canonical_payload())
        if compute_revision_hash(self.canonical_payload()) != self.revision_hash: raise RevisionIntegrityError("revision hash mismatch")
        if registry is not None:
            trigger = registry.get(self.trigger_consensus_hash)
            if trigger is None: raise RevisionIntegrityError("consensus substitution or missing consensus")
            verifier = getattr(trigger, "verify", None)
            if callable(verifier):
                try: verified = verifier(registry)
                except TypeError: verified = verifier()
                if verified is not True: raise RevisionIntegrityError("consensus integrity verification failed")
            if _status(trigger) != self.trigger_status: raise RevisionIntegrityError("trigger status mismatch")
            if tuple(_upstream(trigger)) != tuple(self.provenance["upstream_chain"]): raise RevisionIntegrityError("upstream provenance mismatch")
        if parent_hypothesis is not None and parent_hypothesis.hypothesis_hash != self.parent_hypothesis_hash: raise RevisionIntegrityError("ancestor substitution detected")
        if self.lineage != (self.parent_hypothesis_hash, self.revision_hash): raise RevisionIntegrityError("incomplete descendant lineage")
        if self.trigger_consensus_hash in self.lineage or self.parent_hypothesis_hash in self.provenance["upstream_chain"]: raise RevisionIntegrityError("circular dependency detected")
        return True

    def export(self) -> Mapping[str, Any]:
        return _plain({"revision_hash": self.revision_hash, **self.canonical_payload(), "lineage": self.lineage})

def make_revision(*, parent_hypothesis: HypothesisRecord, trigger: Any, registry: Mapping[str, Any], formulation: str, revision_type: str, revision_method: str, parameters: Mapping[str, Any], epistemic_status: str, rationale: Mapping[str, Any]) -> RevisionRecord:
    if not isinstance(parent_hypothesis, HypothesisRecord): raise RevisionIntegrityError("parent_hypothesis must be a HypothesisRecord")
    if parent_hypothesis.status not in {HypothesisStatus.REFUTED, HypothesisStatus.REVISED}: raise RevisionIntegrityError("unsupported revision: parent must be REFUTED or REVISED")
    trigger_hash = getattr(trigger, "consensus_hash", None); _hash_id(trigger_hash, "trigger_consensus_hash")
    if registry.get(trigger_hash) is not trigger: raise RevisionIntegrityError("consensus must be registry-backed")
    verifier = getattr(trigger, "verify", None)
    if not callable(verifier): raise RevisionIntegrityError("consensus verifier is required")
    try: verified = verifier(registry)
    except TypeError: verified = verifier()
    if verified is not True: raise RevisionIntegrityError("consensus integrity verification failed")
    trigger_status = _status(trigger)
    if not isinstance(formulation, str) or not formulation.strip() or not isinstance(revision_method, str) or not revision_method.strip(): raise RevisionIntegrityError("formulation and method are required")
    if revision_type not in _TYPES: raise RevisionIntegrityError("invalid revision_type")
    if epistemic_status not in _EPISTEMIC: raise RevisionIntegrityError("invalid epistemic status")
    if not isinstance(rationale, Mapping) or not rationale: raise RevisionIntegrityError("content-addressed revision rationale is required")
    _check(parameters); _check(rationale)
    upstream = _upstream(trigger)
    if parent_hypothesis.hypothesis_hash in upstream or trigger_hash in upstream: raise RevisionIntegrityError("circular dependency detected")
    srcprov = getattr(trigger, "provenance", {}) or {}
    provenance = {"upstream_chain": list(upstream), "interpretation_hashes": list(getattr(trigger, "interpretation_hashes", srcprov.get("interpretation_hashes", ()))), "result_hashes": list(getattr(trigger, "result_hashes", srcprov.get("result_hashes", ()))), "execution_hashes": list(getattr(trigger, "execution_hashes", srcprov.get("execution_hashes", ()))), "plan_hashes": list(getattr(trigger, "plan_hashes", srcprov.get("plan_hashes", ()))), "question_hashes": list(getattr(trigger, "question_hashes", srcprov.get("question_hashes", ()))), "trace_hashes": list(getattr(trigger, "trace_hashes", srcprov.get("trace_hashes", ()))), "state_hashes": list(getattr(trigger, "state_hashes", srcprov.get("state_hashes", ())))}
    for key, values in provenance.items():
        for value in values: _hash_id(value, key)
    loop = {"parent_hypothesis_hash": parent_hypothesis.hypothesis_hash, "trigger_consensus_hash": trigger_hash, "historical_status": parent_hypothesis.status.value}
    material = {"parent_hypothesis_hash": parent_hypothesis.hypothesis_hash, "trigger_consensus_hash": trigger_hash, "trigger_status": trigger_status.value, "formulation": " ".join(formulation.split()), "revision_type": revision_type, "revision_method": revision_method.strip(), "parameters": _plain(parameters), "epistemic_status": epistemic_status, "rationale": _plain(rationale), "provenance": provenance, "loop_closure": loop}
    revision_hash = compute_revision_hash(material)
    rec = RevisionRecord(revision_hash, parent_hypothesis.hypothesis_hash, trigger_hash, trigger_status, material["formulation"], revision_type, material["revision_method"], _freeze(parameters), epistemic_status, _freeze(rationale), _freeze(provenance), _freeze(loop), (parent_hypothesis.hypothesis_hash, revision_hash))
    rec.verify(registry=registry, parent_hypothesis=parent_hypothesis)
    return rec
