"""P19.4 deterministic research-result and provenance projection.

Research-only module. Result identity is content-addressed from the verified
P19.3 trajectory plus canonical research outcome and bounded provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_bytes
from .replay import ReplayTrace, compute_trace_hash


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RESULT_TYPES = frozenset({"finding", "measurement", "hypothesis", "conclusion"})
_PROVENANCE_KEYS = frozenset({"source", "operation", "version"})
_RUNTIME_KEYS = frozenset({
    "timestamp",
    "uuid",
    "memory_address",
    "environment",
    "local_path",
    "hostname",
    "pid",
    "process_id",
})


class ResultError(ValueError):
    """Base error for deterministic research-result projection failures."""


class ResultIntegrityError(ResultError):
    """Raised when a result or bound trajectory fails cryptographic validation."""


class ResultTypeError(ResultError):
    """Raised when a result type is not part of the stable result vocabulary."""


class ResultProvenanceError(ResultError):
    """Raised when provenance violates the deterministic schema."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
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
        raise ResultIntegrityError(f"{field} must be a lowercase SHA-256 hex digest")


def _validate_type(result_type: str) -> None:
    if result_type not in _RESULT_TYPES:
        raise ResultTypeError(f"unknown result_type: {result_type!r}")


def _validate_provenance(provenance: Mapping[str, Any]) -> None:
    if not isinstance(provenance, Mapping):
        raise ResultProvenanceError("provenance must be a mapping")
    keys = set(provenance)
    if keys != _PROVENANCE_KEYS:
        raise ResultProvenanceError("provenance must contain exactly source, operation, version")
    if keys & _RUNTIME_KEYS:
        raise ResultProvenanceError("runtime metadata is forbidden in provenance")
    if any(not isinstance(provenance[key], str) or not provenance[key] for key in _PROVENANCE_KEYS):
        raise ResultProvenanceError("provenance values must be non-empty strings")


def compute_result_hash(
    trace_hash: str,
    result_type: str,
    result_payload: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> str:
    """Return the canonical SHA-256 identity of a research result."""
    _validate_hash(trace_hash, "trace_hash")
    _validate_type(result_type)
    if not isinstance(result_payload, Mapping):
        raise ResultError("result_payload must be a mapping")
    _validate_provenance(provenance)
    material = {
        "trace_hash": trace_hash,
        "result_type": result_type,
        "result_payload": _thaw(result_payload),
        "provenance": _thaw(provenance),
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchResult:
    """Immutable cryptographic record of a research outcome bound to one trace."""

    trace_hash: str
    result_type: str
    result_payload: Mapping[str, Any]
    provenance: Mapping[str, str]
    result_hash: str

    def __post_init__(self) -> None:
        _validate_hash(self.trace_hash, "trace_hash")
        _validate_type(self.result_type)
        if not isinstance(self.result_payload, Mapping):
            raise ResultError("result_payload must be a mapping")
        _validate_provenance(self.provenance)
        object.__setattr__(self, "result_payload", _freeze(dict(self.result_payload)))
        object.__setattr__(self, "provenance", _freeze(dict(self.provenance)))
        expected = compute_result_hash(
            self.trace_hash,
            self.result_type,
            self.result_payload,
            self.provenance,
        )
        if self.result_hash != expected:
            raise ResultIntegrityError("result_hash does not match result content")

    def verify_integrity(self) -> bool:
        """Return whether result_hash matches the current result content."""
        try:
            return self.result_hash == compute_result_hash(
                self.trace_hash,
                self.result_type,
                self.result_payload,
                self.provenance,
            )
        except ResultError:
            return False

    def verify(self) -> bool:
        """Raise on integrity failure; return True only for a valid result."""
        if not self.verify_integrity():
            raise ResultIntegrityError("research result integrity failure")
        return True


def project_result(
    trace: ReplayTrace,
    result_type: str,
    result_payload: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> ResearchResult:
    """Bind a deterministic research outcome to a self-consistent P19.3 trace."""
    _validate_hash(trace.trace_hash, "trace_hash")
    expected_trace_hash = compute_trace_hash(
        trace.initial_state_hash,
        trace.ordered_event_ids,
        trace.resulting_state_hash,
    )
    if trace.trace_hash != expected_trace_hash:
        raise ResultIntegrityError("replay trace integrity failure")
    result_hash = compute_result_hash(trace.trace_hash, result_type, result_payload, provenance)
    return ResearchResult(
        trace_hash=trace.trace_hash,
        result_type=result_type,
        result_payload=result_payload,
        provenance=provenance,
        result_hash=result_hash,
    )
