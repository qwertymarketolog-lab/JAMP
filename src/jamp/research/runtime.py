"""P21.1 deterministic research runtime/orchestrator.

This module only routes and verifies already-created research artifacts. It adds
no scientific inference, storage, networking, filesystem access, or production
domain dependency. Runtime identity is derived solely from canonical research
inputs and content-addressed upstream identities.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = frozenset({
    "timestamp", "uuid", "memory_address", "environment", "local_path",
    "hostname", "pid", "process_id",
})


class RuntimeErrorBase(ValueError):
    """Base error for deterministic runtime validation."""


class RuntimeIntegrityError(RuntimeErrorBase):
    """Raised when an integrated research chain is invalid or tampered with."""


class RuntimeStage(str, Enum):
    QUESTION = "QUESTION"
    PLAN = "PLAN"
    EXECUTION = "EXECUTION"
    RESULT = "RESULT"
    INTERPRETATION = "INTERPRETATION"
    CONSENSUS = "CONSENSUS"
    REVISION = "REVISION"


class RuntimeStatus(str, Enum):
    VERIFIED = "VERIFIED"


_ALLOWED = {
    RuntimeStage.QUESTION: frozenset({RuntimeStage.PLAN}),
    RuntimeStage.PLAN: frozenset({RuntimeStage.EXECUTION}),
    RuntimeStage.EXECUTION: frozenset({RuntimeStage.RESULT}),
    RuntimeStage.RESULT: frozenset({RuntimeStage.INTERPRETATION}),
    RuntimeStage.INTERPRETATION: frozenset({RuntimeStage.CONSENSUS}),
    RuntimeStage.CONSENSUS: frozenset({RuntimeStage.REVISION}),
    RuntimeStage.REVISION: frozenset({RuntimeStage.QUESTION}),
}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value):
            raise RuntimeIntegrityError("runtime metadata is forbidden")
        if any(not isinstance(k, str) for k in value):
            raise RuntimeIntegrityError("mapping keys must be strings")
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
    if isinstance(value, Enum):
        return value.value
    return value


def _hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise RuntimeIntegrityError(f"{field} must be lowercase SHA-256")


def _artifact_hash(artifact: Any) -> str:
    value = getattr(artifact, "artifact_hash", None) or getattr(artifact, "result_hash", None)
    if value is None and hasattr(artifact, "export"):
        exported = artifact.export()
        value = exported.get("artifact_hash") or exported.get("result_hash")
    _hash(value, "artifact_hash")
    return value


def _artifact_export(artifact: Any) -> Mapping[str, Any]:
    if hasattr(artifact, "export"):
        exported = artifact.export()
        if not isinstance(exported, Mapping):
            raise RuntimeIntegrityError("artifact export must be a mapping")
        return exported
    return {}


def _verify_artifact(artifact: Any, expected_hash: str) -> None:
    actual = _artifact_hash(artifact)
    if actual != expected_hash:
        raise RuntimeIntegrityError("artifact identity substitution detected")
    verify = getattr(artifact, "verify", None)
    if callable(verify):
        try:
            verified = verify()
        except TypeError:
            verified = verify(registry=None)
        except Exception as exc:
            raise RuntimeIntegrityError("upstream artifact verification failed") from exc
        if verified is False:
            raise RuntimeIntegrityError("upstream artifact verification failed")
    exported = _artifact_export(artifact)
    exported_hash = exported.get("artifact_hash") or exported.get("result_hash")
    if exported_hash is not None and exported_hash != expected_hash:
        raise RuntimeIntegrityError("exported artifact identity substitution detected")


def _reference_values(artifact: Any) -> set[str]:
    values: set[str] = set()
    for name in (
        "question_hash", "plan_hash", "execution_hash", "result_hash",
        "interpretation_hash", "consensus_hash", "revision_hash",
        "parent_question_hash", "parent_hypothesis_hash", "trigger_reference",
    ):
        value = getattr(artifact, name, None)
        if isinstance(value, str):
            values.add(value)
    exported = _artifact_export(artifact)
    for name in (
        "question_hash", "plan_hash", "execution_hash", "result_hash",
        "interpretation_hash", "consensus_hash", "revision_hash",
        "parent_question_hash", "parent_hypothesis_hash", "trigger_reference",
    ):
        value = exported.get(name)
        if isinstance(value, str):
            values.add(value)
    upstream = getattr(artifact, "upstream_hash", None)
    if isinstance(upstream, str):
        values.add(upstream)
    if isinstance(exported.get("upstream_hash"), str):
        values.add(exported["upstream_hash"])
    return values


def _lineage(artifact: Any, own_hash: str) -> tuple[str, ...]:
    value = getattr(artifact, "provenance_chain", None)
    if value is None:
        exported = _artifact_export(artifact)
        value = exported.get("provenance_chain", exported.get("provenance", ()))
    if isinstance(value, Mapping):
        flattened: list[str] = []
        for item in value.values():
            if isinstance(item, str) and _HASH_RE.fullmatch(item):
                flattened.append(item)
            elif isinstance(item, (list, tuple)):
                flattened.extend(x for x in item if isinstance(x, str) and _HASH_RE.fullmatch(x))
        value = flattened
    if isinstance(value, (str, bytes)):
        value = ()
    try:
        items = tuple(x for x in value if isinstance(x, str))
    except TypeError:
        items = ()
    for item in items:
        _hash(item, "provenance hash")
    if own_hash not in items:
        items = items + (own_hash,)
    return tuple(dict.fromkeys(items))


def _validate_transitions(transitions: Sequence[RuntimeStage]) -> None:
    if not transitions:
        raise RuntimeIntegrityError("at least one stage is required")
    if len(set(transitions)) != len(transitions):
        raise RuntimeIntegrityError("cyclic runtime stage identity is forbidden")
    for left, right in zip(transitions, transitions[1:]):
        if right not in _ALLOWED[left]:
            raise RuntimeIntegrityError(f"illegal transition {left.value}->{right.value}")


def compute_runtime_hash(
    context: Mapping[str, Any],
    transitions: Sequence[RuntimeStage | str],
    artifact_hashes: Mapping[RuntimeStage | str, str],
) -> str:
    stages = tuple(x.value if isinstance(x, RuntimeStage) else x for x in transitions)
    normalized = {str(k.value if isinstance(k, RuntimeStage) else k): v for k, v in artifact_hashes.items()}
    material = {
        "context": _thaw(_freeze(context)),
        "transitions": list(stages),
        "artifact_hashes": {k: normalized[k] for k in sorted(normalized)},
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


@dataclass(frozen=True, slots=True)
class ResearchRuntime:
    context: Mapping[str, Any]
    transitions: tuple[RuntimeStage, ...]
    artifact_hashes: Mapping[RuntimeStage, str]
    provenance: Mapping[str, Any]
    status: RuntimeStatus
    runtime_hash: str

    def __post_init__(self) -> None:
        context = _freeze(self.context)
        transitions = tuple(RuntimeStage(x) if not isinstance(x, RuntimeStage) else x for x in self.transitions)
        artifacts = _freeze(self.artifact_hashes)
        provenance = _freeze(self.provenance)
        _validate_transitions(transitions)
        if self.status is not RuntimeStatus.VERIFIED:
            raise RuntimeIntegrityError("invalid runtime status")
        for value in artifacts.values():
            _hash(value, "artifact_hash")
        expected = compute_runtime_hash(context, transitions, artifacts)
        if expected != self.runtime_hash:
            raise RuntimeIntegrityError("runtime_hash does not match content")
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "transitions", transitions)
        object.__setattr__(self, "artifact_hashes", artifacts)
        object.__setattr__(self, "provenance", provenance)

    def verify(self) -> bool:
        _validate_transitions(self.transitions)
        expected = compute_runtime_hash(self.context, self.transitions, self.artifact_hashes)
        if expected != self.runtime_hash:
            raise RuntimeIntegrityError("runtime integrity failure")
        return True

    def reconstruct_chain(self) -> tuple[str, ...]:
        return self.transitions

    def export(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "context": _thaw(self.context),
            "transitions": [x.value for x in self.transitions],
            "artifact_hashes": {k.value: v for k, v in self.artifact_hashes.items()},
            "provenance": _thaw(self.provenance),
            "status": self.status.value,
            "runtime_hash": self.runtime_hash,
        })

    @classmethod
    def from_export(cls, payload: Mapping[str, Any]) -> "ResearchRuntime":
        if not isinstance(payload, Mapping):
            raise RuntimeIntegrityError("invalid runtime export")
        required = {"context", "transitions", "artifact_hashes", "provenance", "status", "runtime_hash"}
        if set(payload) != required:
            raise RuntimeIntegrityError("invalid runtime export schema")
        return cls(
            context=payload["context"],
            transitions=tuple(RuntimeStage(x) for x in payload["transitions"]),
            artifact_hashes={RuntimeStage(k): v for k, v in payload["artifact_hashes"].items()},
            provenance=payload["provenance"],
            status=RuntimeStatus(payload["status"]),
            runtime_hash=payload["runtime_hash"],
        )


def make_runtime(
    *,
    context: Mapping[str, Any],
    transitions: Sequence[RuntimeStage | str],
    artifacts: Mapping[RuntimeStage | str, Any],
) -> ResearchRuntime:
    """Verify and deterministically route an existing research artifact chain."""
    context_frozen = _freeze(context)
    stages = tuple(RuntimeStage(x) if not isinstance(x, RuntimeStage) else x for x in transitions)
    _validate_transitions(stages)
    normalized: dict[RuntimeStage, Any] = {}
    for key, value in artifacts.items():
        stage = RuntimeStage(key) if not isinstance(key, RuntimeStage) else key
        normalized[stage] = value
    if set(normalized) != set(stages):
        raise RuntimeIntegrityError("artifacts must match runtime stages exactly")

    hashes: dict[RuntimeStage, str] = {}
    lineages: dict[str, tuple[str, ...]] = {}
    previous_hash: str | None = None
    for stage in stages:
        artifact = normalized[stage]
        current_hash = _artifact_hash(artifact)
        _verify_artifact(artifact, current_hash)
        refs = _reference_values(artifact)
        if previous_hash is not None and previous_hash not in refs:
            raise RuntimeIntegrityError(
                f"{stage.value} artifact does not bind to previous upstream artifact"
            )
        hashes[stage] = current_hash
        lineages[stage.value] = _lineage(artifact, current_hash)
        previous_hash = current_hash

    provenance = {
        "stages": tuple(stage.value for stage in stages),
        "artifact_hashes": tuple(hashes[stage] for stage in stages),
        "lineage": tuple(lineages[stage.value] for stage in stages),
        "recursive": True,
    }
    runtime_hash = compute_runtime_hash(context_frozen, stages, hashes)
    return ResearchRuntime(
        context=context_frozen,
        transitions=stages,
        artifact_hashes=hashes,
        provenance=provenance,
        status=RuntimeStatus.VERIFIED,
        runtime_hash=runtime_hash,
    )
