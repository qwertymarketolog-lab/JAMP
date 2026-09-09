"""P21.4 system-wide adversarial verification over the existing research stack.

This is a proof harness, not a scientific engine. It accepts immutable,
content-addressed stage objects, independently rechecks their identities and
parent links, binds the chain to the existing P21 runtime/session layers, and
exposes deterministic evidence for tamper propagation. No storage, network,
filesystem, production-domain, randomness, or inference is used.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .runtime import RuntimeStage, RuntimeStatus, ResearchRuntime
from .session import ResearchSession

_HASH = re.compile(r"^[0-9a-f]{64}$")
_KINDS = ("question", "plan", "execution", "result", "interpretation", "consensus", "revision")
_RUNTIME_KEYS = frozenset({"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id", "runtime", "host", "platform"})

class AuditIntegrityError(ValueError):
    """Raised when a full-chain proof detects invalid or substituted data."""

def _hash(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _HASH.fullmatch(value): raise AuditIntegrityError(f"{field} must be lowercase SHA-256")

def _check_runtime_metadata(value: Any) -> None:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value): raise AuditIntegrityError("runtime metadata is forbidden")
        for key, item in value.items():
            if not isinstance(key, str): raise AuditIntegrityError("mapping keys must be strings")
            _check_runtime_metadata(item)
    elif isinstance(value, (list, tuple)):
        for item in value: _check_runtime_metadata(item)

def _artifact_hash(artifact: Any) -> str:
    value = getattr(artifact, "artifact_hash", None) or getattr(artifact, "result_hash", None)
    _hash(value, "artifact_hash"); return value

def _export(artifact: Any) -> Mapping[str, Any]:
    fn = getattr(artifact, "export", None)
    if not callable(fn): raise AuditIntegrityError("artifact export is required")
    value = fn()
    if not isinstance(value, Mapping): raise AuditIntegrityError("artifact export must be a mapping")
    return value

def _verify(artifact: Any) -> None:
    fn = getattr(artifact, "verify", None)
    if not callable(fn): raise AuditIntegrityError("independent artifact verifier is required")
    try: result = fn()
    except Exception as exc: raise AuditIntegrityError("artifact integrity verification failed") from exc
    if result is not True: raise AuditIntegrityError("artifact integrity verification failed")

@dataclass(frozen=True, slots=True)
class _RuntimeAdapter:
    artifact: Any
    @property
    def artifact_hash(self) -> str: return _artifact_hash(self.artifact)
    @property
    def upstream_hash(self) -> str | None: return getattr(self.artifact, "parent_hash", None)
    def export(self) -> Mapping[str, Any]:
        value = dict(_export(self.artifact)); value["upstream_hash"] = self.upstream_hash; return value
    def verify(self) -> bool: _verify(self.artifact); return True

@dataclass(frozen=True, slots=True)
class FullChainAudit:
    artifacts: tuple[Any, ...]
    session: ResearchSession
    runtime: ResearchRuntime
    audit_hash: str
    provenance: tuple[str, ...]
    integration_layers: tuple[str, ...] = ("P19", "P20", "P21")
    stage_names: tuple[str, ...] = tuple(x.value for x in RuntimeStage)

    @property
    def session_hash(self) -> str: return self.session.session_hash

    @classmethod
    def create(cls, artifacts: Sequence[Any], *, session: ResearchSession, runtime_metadata: Mapping[str, Any] | None = None) -> "FullChainAudit":
        if runtime_metadata is not None:
            _check_runtime_metadata(runtime_metadata)
            if runtime_metadata: raise AuditIntegrityError("runtime metadata is forbidden")
        items = tuple(artifacts)
        if len(items) != len(_KINDS): raise AuditIntegrityError("exactly seven ordered research stages are required")
        if tuple(getattr(x, "kind", None) for x in items) != _KINDS: raise AuditIntegrityError("full-chain stage order mismatch")
        if not isinstance(session, ResearchSession) or not session.verify(): raise AuditIntegrityError("invalid research session")
        _check_runtime_metadata(session.metadata)
        hashes: list[str] = []; previous: str | None = None
        for index, (kind, artifact) in enumerate(zip(_KINDS, items)):
            own = _artifact_hash(artifact); exported = _export(artifact)
            exported_hash = exported.get("artifact_hash") or exported.get("result_hash")
            if exported_hash != own: raise AuditIntegrityError("artifact identity substitution detected")
            _check_runtime_metadata(exported); _verify(artifact)
            parent = getattr(artifact, "parent_hash", None)
            if index == 0:
                if parent is not None: raise AuditIntegrityError("root question cannot have an upstream parent")
            elif parent != previous: raise AuditIntegrityError(f"{kind} does not bind to previous stage")
            if parent == own: raise AuditIntegrityError("self-cycle detected")
            hashes.append(own); previous = own
        expected_session_refs = {kind: tuple(sorted({h for a, h in zip(items, hashes) if getattr(a, "kind", None) == kind})) for kind in session.indexes}
        for kind, refs in expected_session_refs.items():
            if tuple(session.indexes[kind]) != refs: raise AuditIntegrityError("session membership does not match chain")
        adapters = tuple(_RuntimeAdapter(x) for x in items)
        stages = tuple(RuntimeStage(x.upper()) for x in _KINDS)
        from .runtime import make_runtime
        runtime = make_runtime(context={"purpose": "P21.4"}, transitions=stages, artifacts={stage: adapter for stage, adapter in zip(stages, adapters)})
        material = {"session_hash": session.session_hash, "runtime_hash": runtime.runtime_hash, "stages": list(_KINDS), "artifact_hashes": hashes, "provenance": hashes}
        audit_hash = hashlib.sha256(canonical_bytes(material)).hexdigest()
        return cls(items, session, runtime, audit_hash, tuple(hashes))

    def verify_independent(self) -> bool:
        rebuilt = FullChainAudit.create(self.artifacts, session=self.session)
        if rebuilt.audit_hash != self.audit_hash: raise AuditIntegrityError("full-chain audit hash mismatch")
        if rebuilt.runtime.runtime_hash != self.runtime.runtime_hash: raise AuditIntegrityError("runtime hash mismatch")
        return True

    def canonical_bytes(self) -> bytes:
        return canonical_bytes({"session_hash": self.session.session_hash, "runtime_hash": self.runtime.runtime_hash, "artifact_hashes": list(self.provenance), "audit_hash": self.audit_hash})

    def export(self) -> dict[str, Any]:
        return {"audit_hash": self.audit_hash, "session_hash": self.session.session_hash, "runtime_hash": self.runtime.runtime_hash, "stages": list(self.stage_names), "provenance": list(self.provenance), "integration_layers": list(self.integration_layers), "status": RuntimeStatus.VERIFIED.value}
