"""P20.2 deterministic cross-trajectory composition.

Research-only functionality. A composition is an immutable, content-addressed
projection over verified registry artifacts and their complete replay provenance.
Source artifacts are never modified.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes
from .registry import ArtifactRegistry, RegistryIntegrityError


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = frozenset(
    {
        "time" + "stamp",
        "u" + "uid",
        "memory" + "_address",
        "environ" + "ment",
        "local" + "_path",
        "host" + "name",
        "p" + "id",
        "process" + "_id",
    }
)


class CompositionError(ValueError):
    """Base composition error."""


class CompositionIntegrityError(CompositionError):
    """Raised when a composition or one of its inputs is inconsistent."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(key in _RUNTIME_KEYS for key in value):
            raise CompositionIntegrityError("runtime metadata is forbidden")
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
        raise CompositionIntegrityError(f"{field} must be a lowercase SHA-256 hex digest")


def compute_composition_hash(
    result_hashes: Sequence[str],
    semantics: Mapping[str, Any],
) -> str:
    """Return the canonical identity of a composition.

    Constituent order is canonicalized because P20.2 defines composition as an
    unordered aggregation. Multiplicity remains significant.
    """
    if not isinstance(semantics, Mapping):
        raise CompositionError("semantics must be a mapping")
    canonical_hashes = tuple(sorted(result_hashes))
    for result_hash in canonical_hashes:
        _validate_hash(result_hash, "result_hash")
    frozen_semantics = _freeze(dict(semantics))
    material = {
        "result_hashes": list(canonical_hashes),
        "semantics": _thaw(frozen_semantics),
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


@dataclass(frozen=True, slots=True)
class CompositionArtifact:
    """Immutable content-addressed projection of registered research results."""

    result_hashes: tuple[str, ...]
    semantics: Mapping[str, Any]
    provenance: Mapping[str, Mapping[str, str]]
    trace_hashes: Mapping[str, str]
    event_ids: Mapping[str, tuple[str, ...]]
    state_anchors: Mapping[str, tuple[str, str]]
    composition_hash: str

    def __post_init__(self) -> None:
        canonical_hashes = tuple(sorted(self.result_hashes))
        if canonical_hashes != tuple(self.result_hashes):
            raise CompositionIntegrityError("result_hashes must use canonical order")
        for result_hash in self.result_hashes:
            _validate_hash(result_hash, "result_hash")
        object.__setattr__(self, "result_hashes", canonical_hashes)
        object.__setattr__(self, "semantics", _freeze(dict(self.semantics)))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))
        object.__setattr__(self, "trace_hashes", _freeze(dict(self.trace_hashes)))
        object.__setattr__(self, "event_ids", _freeze(dict(self.event_ids)))
        object.__setattr__(self, "state_anchors", _freeze(dict(self.state_anchors)))
        expected = compute_composition_hash(self.result_hashes, self.semantics)
        if self.composition_hash != expected:
            raise CompositionIntegrityError("composition_hash does not match composition content")

    def verify(self, registry: ArtifactRegistry) -> bool:
        """Verify inputs, provenance and composition identity against a registry."""
        expected = compose_results(
            registry,
            self.result_hashes,
            semantics=self.semantics,
        )
        if expected != self:
            raise CompositionIntegrityError("composition integrity failure")
        return True


def compose_results(
    registry: ArtifactRegistry,
    result_hashes: Sequence[str],
    *,
    semantics: Mapping[str, Any] | None = None,
) -> CompositionArtifact:
    """Compose verified registry results without rewriting their source records."""
    if not isinstance(registry, ArtifactRegistry):
        raise CompositionError("registry must be an ArtifactRegistry")
    if semantics is None:
        semantics = {}
    if not isinstance(semantics, Mapping):
        raise CompositionError("semantics must be a mapping")

    canonical_hashes = tuple(sorted(result_hashes))
    provenance: dict[str, Mapping[str, str]] = {}
    trace_hashes: dict[str, str] = {}
    event_ids: dict[str, tuple[str, ...]] = {}
    state_anchors: dict[str, tuple[str, str]] = {}

    for result_hash in canonical_hashes:
        _validate_hash(result_hash, "result_hash")
        if not registry.contains(result_hash):
            raise CompositionIntegrityError("unknown result_hash")
        try:
            result = registry.get(result_hash)
            entry = registry.index[result_hash]
        except (KeyError, RegistryIntegrityError) as exc:
            raise CompositionIntegrityError("registered input failed integrity verification") from exc

        if not result.verify_integrity():
            raise CompositionIntegrityError("input result integrity failure")
        if entry.get("trace_hash") != result.trace_hash:
            raise CompositionIntegrityError("result/registry trace mismatch")
        required = ("initial_state_hash", "ordered_event_ids", "resulting_state_hash")
        if not all(key in entry for key in required):
            raise CompositionIntegrityError("complete replay provenance is required")

        provenance[result_hash] = result.provenance
        trace_hashes[result_hash] = result.trace_hash
        event_ids[result_hash] = tuple(entry["ordered_event_ids"])
        state_anchors[result_hash] = (
            entry["initial_state_hash"],
            entry["resulting_state_hash"],
        )

    frozen_semantics = _freeze(dict(semantics))
    composition_hash = compute_composition_hash(canonical_hashes, frozen_semantics)
    return CompositionArtifact(
        result_hashes=canonical_hashes,
        semantics=frozen_semantics,
        provenance=provenance,
        trace_hashes=trace_hashes,
        event_ids=event_ids,
        state_anchors=state_anchors,
        composition_hash=composition_hash,
    )
