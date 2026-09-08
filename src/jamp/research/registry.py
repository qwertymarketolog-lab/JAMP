"""P20.1 immutable, content-addressed research artifact registry.

Research-only module. The registry is deterministic and in-memory: result_hash is
its content address, while the immutable index records the provenance chain from
result_hash back through trace_hash to the replay state anchors.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_bytes as _canonical_bytes
from .replay import ReplayTrace, compute_trace_hash
from .result import ResearchResult


class RegistryError(ValueError):
    """Base registry error."""


class RegistryIntegrityError(RegistryError):
    """Raised when an artifact, trace, or index entry is inconsistent."""


@dataclass(frozen=True, slots=True)
class _Artifact:
    result: ResearchResult
    trace: ReplayTrace | None = None


class ArtifactRegistry:
    """Deterministic in-memory registry keyed exclusively by ``result_hash``."""

    __slots__ = ("_artifacts", "_index")

    def __init__(self) -> None:
        self._artifacts: dict[str, _Artifact] = {}
        self._index: dict[str, Mapping[str, Any]] = {}

    @property
    def index(self) -> Mapping[str, Mapping[str, Any]]:
        """Return an immutable provenance index snapshot."""
        return MappingProxyType(dict(self._index))

    def __len__(self) -> int:
        return len(self._artifacts)

    def contains(self, result_hash: str) -> bool:
        return result_hash in self._artifacts

    def register(
        self,
        result: ResearchResult,
        trace: ReplayTrace | None = None,
    ) -> ResearchResult:
        """Register one result idempotently after complete identity validation."""
        if not isinstance(result, ResearchResult):
            raise RegistryIntegrityError("artifact must be a ResearchResult")
        if not result.verify_integrity():
            raise RegistryIntegrityError("artifact result_hash integrity failure")

        if trace is not None:
            expected_trace_hash = compute_trace_hash(
                trace.initial_state_hash,
                trace.ordered_event_ids,
                trace.resulting_state_hash,
            )
            if trace.trace_hash != expected_trace_hash:
                raise RegistryIntegrityError("trace_hash integrity failure")
            if trace.trace_hash != result.trace_hash:
                raise RegistryIntegrityError("result/trace provenance mismatch")

        existing = self._artifacts.get(result.result_hash)
        if existing is not None:
            if existing.result != result or existing.trace != trace:
                raise RegistryIntegrityError("content-address collision or provenance mismatch")
            return existing.result

        index_entry: dict[str, Any] = {"trace_hash": result.trace_hash}
        if trace is not None:
            index_entry.update({
                "initial_state_hash": trace.initial_state_hash,
                "ordered_event_ids": tuple(trace.ordered_event_ids),
                "resulting_state_hash": trace.resulting_state_hash,
            })
        frozen_entry = MappingProxyType(index_entry)
        self._artifacts[result.result_hash] = _Artifact(result, trace)
        self._index[result.result_hash] = frozen_entry
        return result

    def get(self, result_hash: str) -> ResearchResult:
        """Retrieve an artifact by its immutable content address."""
        artifact = self._artifacts[result_hash]
        if not artifact.result.verify_integrity():
            raise RegistryIntegrityError("stored artifact integrity failure")
        self._verify_index_entry(result_hash, artifact)
        return artifact.result

    def verify(self, result_hash: str) -> bool:
        """Verify artifact content and its indexed provenance chain."""
        self.get(result_hash)
        return True

    def verify_index(self, result_hash: str, expected_trace_hash: str) -> bool:
        """Verify that an indexed result points to the supplied trace hash."""
        entry = self._index[result_hash]
        if entry.get("trace_hash") != expected_trace_hash:
            raise RegistryIntegrityError("provenance index mismatch")
        self._verify_index_entry(result_hash, self._artifacts[result_hash])
        return True

    def snapshot(self) -> Mapping[str, ResearchResult]:
        """Return a deterministic immutable result-address snapshot."""
        return MappingProxyType({key: self._artifacts[key].result for key in sorted(self._artifacts)})

    def export(self) -> Mapping[str, Any]:
        """Return a deterministic serializable registry representation."""
        artifacts = []
        for result_hash in sorted(self._artifacts):
            artifact = self._artifacts[result_hash]
            result = artifact.result
            item: dict[str, Any] = {
                "result_hash": result.result_hash,
                "trace_hash": result.trace_hash,
                "result_type": result.result_type,
                "result_payload": result.result_payload,
                "provenance": result.provenance,
            }
            if artifact.trace is not None:
                item["trace"] = {
                    "initial_state_hash": artifact.trace.initial_state_hash,
                    "ordered_event_ids": list(artifact.trace.ordered_event_ids),
                    "resulting_state_hash": artifact.trace.resulting_state_hash,
                    "trace_hash": artifact.trace.trace_hash,
                }
            artifacts.append(item)
        return MappingProxyType({"artifacts": tuple(artifacts)})

    @classmethod
    def from_export(cls, exported: Mapping[str, Any]) -> "ArtifactRegistry":
        """Reconstruct a registry from its deterministic export representation."""
        if not isinstance(exported, Mapping) or set(exported) != {"artifacts"}:
            raise RegistryIntegrityError("invalid registry export schema")
        registry = cls()
        for item in exported["artifacts"]:
            if not isinstance(item, Mapping):
                raise RegistryIntegrityError("invalid exported artifact")
            result = ResearchResult(
                trace_hash=item["trace_hash"],
                result_type=item["result_type"],
                result_payload=item["result_payload"],
                provenance=item["provenance"],
                result_hash=item["result_hash"],
            )
            trace_data = item.get("trace")
            trace = None
            if trace_data is not None:
                trace = ReplayTrace(
                    initial_state_hash=trace_data["initial_state_hash"],
                    ordered_event_ids=tuple(trace_data["ordered_event_ids"]),
                    resulting_state_hash=trace_data["resulting_state_hash"],
                    trace_hash=trace_data["trace_hash"],
                )
            registry.register(result, trace)
        return registry

    def _verify_index_entry(self, result_hash: str, artifact: _Artifact) -> None:
        entry = self._index.get(result_hash)
        if entry is None or entry.get("trace_hash") != artifact.result.trace_hash:
            raise RegistryIntegrityError("provenance index integrity failure")
        if artifact.trace is None:
            return
        trace = artifact.trace
        expected = compute_trace_hash(
            trace.initial_state_hash,
            trace.ordered_event_ids,
            trace.resulting_state_hash,
        )
        if trace.trace_hash != expected or entry.get("trace_hash") != trace.trace_hash:
            raise RegistryIntegrityError("stored trace integrity failure")
        if tuple(entry.get("ordered_event_ids", ())) != trace.ordered_event_ids:
            raise RegistryIntegrityError("ordered event index integrity failure")
        if entry.get("initial_state_hash") != trace.initial_state_hash:
            raise RegistryIntegrityError("initial state index integrity failure")
        if entry.get("resulting_state_hash") != trace.resulting_state_hash:
            raise RegistryIntegrityError("resulting state index integrity failure")

    def canonical_bytes(self) -> bytes:
        """Return canonical bytes for the complete deterministic registry state."""
        return _canonical_bytes(self.export())
