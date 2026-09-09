"""P20.3 deterministic evidence derivation and meta-analysis.

Research-only module. Derived evidence is content-addressed and anchored to
verified registry artifacts or verified P20.2 compositions. No I/O, network,
randomness, or production-domain dependencies are permitted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .composition import CompositionArtifact
from .registry import ArtifactRegistry, RegistryIntegrityError


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ANALYSIS_TYPES = frozenset({"OBSERVATION", "COMPARISON", "AGGREGATION", "INFERENCE"})
_RUNTIME_KEYS = frozenset({
    "timestamp", "uuid", "memory_address", "environment", "local_path",
    "hostname", "pid", "process_id",
})


class DerivationError(ValueError):
    """Base P20.3 derivation error."""


class DerivationIntegrityError(DerivationError):
    """Raised when source, provenance, payload, or derived identity is invalid."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(key in _RUNTIME_KEYS for key in value):
            raise DerivationIntegrityError("runtime metadata is forbidden")
        if any(not isinstance(key, str) for key in value):
            raise DerivationIntegrityError("canonical mapping keys must be strings")
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _validate_hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise DerivationIntegrityError(f"{field} must be a lowercase SHA-256 hex digest")


def compute_derived_evidence_hash(
    source_hashes: Sequence[str],
    analysis_type: str,
    algorithm_version: str,
    parameters: Mapping[str, Any],
    result: Mapping[str, Any],
) -> str:
    """Compute deterministic identity from canonical derivation semantics."""
    if analysis_type not in _ANALYSIS_TYPES:
        raise DerivationError(f"unknown analysis_type: {analysis_type!r}")
    if not isinstance(algorithm_version, str) or not algorithm_version:
        raise DerivationError("algorithm_version must be a non-empty string")
    if not isinstance(parameters, Mapping) or not isinstance(result, Mapping):
        raise DerivationError("parameters and result must be mappings")
    canonical_sources = tuple(source_hashes)
    for source_hash in canonical_sources:
        _validate_hash(source_hash, "source_hash")
    material = {
        "source_hashes": list(canonical_sources),
        "analysis_type": analysis_type,
        "algorithm_version": algorithm_version,
        "parameters": _thaw(_freeze(dict(parameters))),
        "result": _thaw(_freeze(dict(result))),
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _source_provenance(registry: ArtifactRegistry, result_hash: str) -> Mapping[str, Any]:
    try:
        result = registry.get(result_hash)
        entry = registry.index[result_hash]
    except (KeyError, RegistryIntegrityError) as exc:
        raise DerivationIntegrityError("registered source failed integrity verification") from exc
    required = ("trace_hash", "initial_state_hash", "ordered_event_ids", "resulting_state_hash")
    if not all(key in entry for key in required):
        raise DerivationIntegrityError("complete replay provenance is required")
    return {
        "result_hash": result.result_hash,
        "trace_hash": result.trace_hash,
        "event_ids": tuple(entry["ordered_event_ids"]),
        "state_anchors": (entry["initial_state_hash"], entry["resulting_state_hash"]),
        "result_provenance": result.provenance,
    }


def _verify_source(
    registry: ArtifactRegistry,
    source: str | CompositionArtifact,
) -> tuple[str, Mapping[str, Any]]:
    if isinstance(source, CompositionArtifact):
        try:
            source.verify(registry)
        except Exception as exc:
            raise DerivationIntegrityError("composition source failed verification") from exc
        leaves = tuple(_source_provenance(registry, h) for h in source.result_hashes)
        return source.composition_hash, {
            "composition_hash": source.composition_hash,
            "result_hashes": source.result_hashes,
            "leaves": leaves,
            "semantics": source.semantics,
        }
    _validate_hash(source, "source_hash")
    return source, _source_provenance(registry, source)


@dataclass(frozen=True, slots=True)
class DerivedEvidence:
    """Immutable content-addressed evidence derived from verified sources."""

    source_hashes: tuple[str, ...]
    analysis_type: str
    algorithm_version: str
    parameters: Mapping[str, Any]
    result: Mapping[str, Any]
    provenance: Mapping[str, Any]
    derived_evidence_hash: str

    def __post_init__(self) -> None:
        if self.analysis_type not in _ANALYSIS_TYPES:
            raise DerivationIntegrityError("invalid analysis_type")
        if not isinstance(self.algorithm_version, str) or not self.algorithm_version:
            raise DerivationIntegrityError("invalid algorithm_version")
        for source_hash in self.source_hashes:
            _validate_hash(source_hash, "source_hash")
        object.__setattr__(self, "source_hashes", tuple(self.source_hashes))
        object.__setattr__(self, "parameters", _freeze(dict(self.parameters)))
        object.__setattr__(self, "result", _freeze(dict(self.result)))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))
        expected = compute_derived_evidence_hash(
            self.source_hashes, self.analysis_type, self.algorithm_version,
            self.parameters, self.result,
        )
        if self.derived_evidence_hash != expected:
            raise DerivationIntegrityError("derived_evidence_hash does not match content")

    def verify(
        self,
        registry: ArtifactRegistry,
        *,
        source_hashes: Sequence[str] | None = None,
    ) -> bool:
        """Recompute source verification, provenance and content identity."""
        expected_sources = tuple(self.source_hashes if source_hashes is None else source_hashes)
        if expected_sources != self.source_hashes:
            raise DerivationIntegrityError("source substitution detected")
        for source_hash in self.source_hashes:
            _source_provenance(registry, source_hash)
        expected = derive_evidence(
            registry, self.source_hashes, self.analysis_type, self.algorithm_version,
            self.parameters, self.result,
        )
        if expected != self:
            raise DerivationIntegrityError("derived evidence integrity failure")
        return True

    def export(self) -> Mapping[str, Any]:
        """Return a deterministic serializable representation."""
        return MappingProxyType({
            "source_hashes": self.source_hashes,
            "analysis_type": self.analysis_type,
            "algorithm_version": self.algorithm_version,
            "parameters": _thaw(self.parameters),
            "result": _thaw(self.result),
            "provenance": _thaw(self.provenance),
            "derived_evidence_hash": self.derived_evidence_hash,
        })


def derive_evidence(
    registry: ArtifactRegistry,
    sources: Sequence[str | CompositionArtifact],
    analysis_type: str,
    algorithm_version: str,
    parameters: Mapping[str, Any],
    result: Mapping[str, Any],
) -> DerivedEvidence:
    """Derive immutable evidence from verified registry-backed sources."""
    if not isinstance(registry, ArtifactRegistry):
        raise DerivationError("registry must be an ArtifactRegistry")
    if analysis_type not in _ANALYSIS_TYPES:
        raise DerivationError(f"unknown analysis_type: {analysis_type!r}")
    if not isinstance(sources, Sequence):
        raise DerivationError("sources must be a sequence")
    if not isinstance(parameters, Mapping) or not isinstance(result, Mapping):
        raise DerivationError("parameters and result must be mappings")
    frozen_parameters = _freeze(dict(parameters))
    frozen_result = _freeze(dict(result))
    if analysis_type == "INFERENCE":
        premises = frozen_parameters.get("premises")
        if not premises:
            raise DerivationIntegrityError("INFERENCE requires explicit non-empty premises")

    verified: list[tuple[str, Mapping[str, Any]]] = []
    for source in sources:
        try:
            verified.append(_verify_source(registry, source))
        except DerivationIntegrityError:
            raise
        except Exception as exc:
            raise DerivationIntegrityError("source verification failed") from exc

    ordered = bool(frozen_parameters.get("ordered", False))
    source_hashes = tuple(item[0] for item in verified) if ordered else tuple(sorted(item[0] for item in verified))
    provenance_items = {item[0]: item[1] for item in verified}
    provenance = {
        "sources": provenance_items,
        "semantic_order": "ordered" if ordered else "unordered",
    }
    derived_hash = compute_derived_evidence_hash(
        source_hashes, analysis_type, algorithm_version, frozen_parameters, frozen_result,
    )
    return DerivedEvidence(
        source_hashes=source_hashes,
        analysis_type=analysis_type,
        algorithm_version=algorithm_version,
        parameters=frozen_parameters,
        result=frozen_result,
        provenance=provenance,
        derived_evidence_hash=derived_hash,
    )
