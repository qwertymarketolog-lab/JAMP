"""P21.2 immutable Research Session / Experiment Ledger.

This module is a packaging and navigation layer only.  It stores immutable
content-addressed identifiers and never owns or mutates upstream artifacts.
No filesystem, network, production-domain, or runtime-metadata dependency is
allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = frozenset({
    "timestamp", "uuid", "memory_address", "environment", "local_path",
    "hostname", "pid", "process_id", "runtime", "host", "platform",
})
_ARTIFACT_KINDS = frozenset({
    "question", "plan", "execution", "result", "interpretation",
    "claim", "consensus", "revision",
})
_STATUS = frozenset({"OPEN", "CLOSED", "ARCHIVED"})


class SessionError(ValueError):
    """Base error for invalid session data."""


class SessionArtifact:
    """Immutable reference to an existing content-addressed research object."""

    __slots__ = ("_kind", "_artifact_hash")

    def __init__(self, kind: str, artifact_hash: str) -> None:
        if kind not in _ARTIFACT_KINDS:
            raise SessionError("unknown artifact kind")
        _validate_hash(artifact_hash, "artifact_hash")
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_artifact_hash", artifact_hash)

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def artifact_hash(self) -> str:
        return self._artifact_hash

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError("SessionArtifact is immutable")


@dataclass(frozen=True)
class ResearchSession:
    """Immutable deterministic index over existing research artifacts."""

    session_hash: str
    metadata: Mapping[str, Any]
    indexes: Mapping[str, tuple[str, ...]]
    status: str

    @classmethod
    def create(
        cls,
        *,
        metadata: Mapping[str, Any],
        artifacts: Sequence[SessionArtifact],
        status: str,
    ) -> "ResearchSession":
        frozen_metadata = _freeze_metadata(metadata)
        if status not in _STATUS:
            raise SessionError("invalid session status")
        if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes)):
            raise SessionError("artifacts must be a sequence of SessionArtifact")
        indexes: dict[str, list[str]] = {kind: [] for kind in sorted(_ARTIFACT_KINDS)}
        for artifact in artifacts:
            if not isinstance(artifact, SessionArtifact):
                raise SessionError("artifact must be SessionArtifact")
            indexes[artifact.kind].append(artifact.artifact_hash)
        normalized = {
            kind: tuple(sorted(set(values)))
            for kind, values in indexes.items()
        }
        proxy_indexes = MappingProxyType(normalized)
        preimage = {
            "metadata": _thaw(frozen_metadata),
            "indexes": {k: list(v) for k, v in proxy_indexes.items()},
            "status": status,
        }
        digest = _digest(preimage)
        return cls(
            session_hash=digest,
            metadata=frozen_metadata,
            indexes=proxy_indexes,
            status=status,
        )

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "metadata": _thaw(self.metadata),
            "indexes": {k: list(v) for k, v in self.indexes.items()},
            "status": self.status,
        }

    def compute_session_hash(self) -> str:
        return _digest(self._identity_payload())

    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self._identity_payload())

    def verify(self) -> bool:
        try:
            _validate_hash(self.session_hash, "session_hash")
            if self.status not in _STATUS:
                return False
            if not isinstance(self.metadata, Mapping) or not isinstance(self.indexes, Mapping):
                return False
            if set(self.indexes) != _ARTIFACT_KINDS:
                return False
            for kind, refs in self.indexes.items():
                if kind not in _ARTIFACT_KINDS or tuple(refs) != tuple(sorted(set(refs))):
                    return False
                for ref in refs:
                    _validate_hash(ref, f"{kind} reference")
            return self.session_hash == self.compute_session_hash()
        except (TypeError, ValueError):
            return False

    def contains(self, kind: str, artifact_hash: str) -> bool:
        _validate_hash(artifact_hash, "artifact_hash")
        if kind not in _ARTIFACT_KINDS:
            raise SessionError("unknown artifact kind")
        return artifact_hash in self.indexes[kind]

    def provenance(self) -> dict[str, tuple[str, ...]]:
        return {kind: tuple(refs) for kind, refs in self.indexes.items() if refs}

    def provenance_chain(self, artifact_hash: str) -> dict[str, str]:
        _validate_hash(artifact_hash, "artifact_hash")
        matches = [kind for kind, refs in self.indexes.items() if artifact_hash in refs]
        if not matches:
            raise SessionError("artifact is not registered in session")
        return {"session": self.session_hash, "kind": matches[0], "result": artifact_hash}

    def export(self) -> str:
        payload = {
            "session_hash": self.session_hash,
            **self._identity_payload(),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_export_payload(cls, payload: Mapping[str, Any]) -> "ResearchSession":
        if not isinstance(payload, Mapping):
            raise SessionError("export payload must be an object")
        try:
            session_hash = payload["session_hash"]
            metadata = payload["metadata"]
            raw_indexes = payload["indexes"]
            status = payload["status"]
        except KeyError as exc:
            raise SessionError("incomplete session export") from exc
        if not isinstance(raw_indexes, Mapping):
            raise SessionError("indexes must be an object")
        artifacts: list[SessionArtifact] = []
        for kind, refs in raw_indexes.items():
            if kind not in _ARTIFACT_KINDS:
                raise SessionError("unknown artifact kind")
            if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
                raise SessionError("artifact index must be a sequence")
            artifacts.extend(SessionArtifact(kind, ref) for ref in refs)
        rebuilt = cls.create(metadata=metadata, artifacts=artifacts, status=status)
        return cls(
            session_hash=session_hash,
            metadata=rebuilt.metadata,
            indexes=rebuilt.indexes,
            status=rebuilt.status,
        )

    @classmethod
    def import_(cls, exported: str) -> "ResearchSession":
        if not isinstance(exported, str):
            raise SessionError("export must be text")
        return cls.from_export_payload(json.loads(exported))

    def with_tampered_hash(self, session_hash: str) -> "ResearchSession":
        return ResearchSession(session_hash, self.metadata, self.indexes, self.status)

    def with_artifact_hash(self, kind: str, artifact_hash: str) -> "ResearchSession":
        if kind not in _ARTIFACT_KINDS:
            raise SessionError("unknown artifact kind")
        _validate_hash(artifact_hash, "artifact_hash")
        altered = {k: tuple(v) for k, v in self.indexes.items()}
        altered[kind] = (artifact_hash,)
        return ResearchSession(self.session_hash, self.metadata, MappingProxyType(altered), self.status)

    def replace_artifact(self, kind: str, artifact_hash: str) -> "ResearchSession":
        raise SessionError("upstream artifact replacement is forbidden")

    def rewrite_upstream(self, kind: str, artifact_hash: str) -> "ResearchSession":
        raise SessionError("upstream identity rewriting is forbidden")


def _validate_hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise SessionError(f"{field} must be lowercase SHA-256")


def _freeze_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SessionError("metadata must be a mapping")
    return MappingProxyType({k: _freeze(v) for k, v in sorted(value.items())})


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value):
            raise SessionError("runtime metadata is forbidden")
        if any(not isinstance(k, str) for k in value):
            raise SessionError("metadata keys must be strings")
        return MappingProxyType({k: _freeze(value[k]) for k in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze(v) for v in value), key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
