from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class InterpretationIntegrityError(ValueError):
    pass


class InterpretationClassification(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    UNDETERMINED = "UNDETERMINED"


_FORBIDDEN = {"timestamp", "uuid", "pid", "process_id", "hostname", "memory_address", "environment", "local_path"}


def _check_runtime(value: Any) -> None:
    if isinstance(value, Mapping):
        for k, v in value.items():
            if str(k).lower() in _FORBIDDEN:
                raise InterpretationIntegrityError(f"runtime metadata forbidden: {k}")
            _check_runtime(v)
    elif isinstance(value, (tuple, list)):
        for v in value:
            _check_runtime(v)


def _canon(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canon(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (tuple, list)):
        return [_canon(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return value


def _hash(payload: Any) -> str:
    raw = json.dumps(_canon(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class InterpretationRecord:
    interpretation_hash: str
    result_hash: str
    analytical_target: Any
    method: str
    parameters: Any
    conclusion: str
    classification: InterpretationClassification
    evidence: Any
    execution_hash: str | None
    question_hash: str | None
    plan_hash: str | None
    trace_hash: str | None
    state_hash: str | None

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "result_hash": self.result_hash,
            "analytical_target": _canon(self.analytical_target),
            "method": self.method,
            "parameters": _canon(self.parameters),
            "conclusion": self.conclusion,
            "classification": self.classification.value,
            "evidence": _canon(self.evidence),
            "execution_hash": self.execution_hash,
            "question_hash": self.question_hash,
            "plan_hash": self.plan_hash,
            "trace_hash": self.trace_hash,
            "state_hash": self.state_hash,
        }

    def verify(self, registry: Mapping[str, Any] | None = None) -> bool:
        if registry is not None:
            result = registry.get(self.result_hash)
            if result is None:
                raise InterpretationIntegrityError("unknown result_hash")
            verifier = getattr(result, "verify", None)
            if callable(verifier) and not verifier():
                raise InterpretationIntegrityError("result integrity failed")
            for attr in ("execution_hash", "question_hash", "plan_hash", "trace_hash", "state_hash"):
                expected = getattr(result, attr, None)
                if expected is not None and getattr(self, attr) != expected:
                    raise InterpretationIntegrityError(f"provenance mismatch: {attr}")
        if _hash(self.canonical_payload()) != self.interpretation_hash:
            raise InterpretationIntegrityError("interpretation hash mismatch")
        if not self.method or not self.conclusion:
            raise InterpretationIntegrityError("method and conclusion are required")
        if not isinstance(self.classification, InterpretationClassification):
            raise InterpretationIntegrityError("invalid classification")
        _check_runtime(self.canonical_payload())
        return True

    def export(self) -> dict[str, Any]:
        self.verify()
        return {"interpretation_hash": self.interpretation_hash, **self.canonical_payload()}


def make_interpretation(*, result_hash: str, analytical_target: Any, method: str, parameters: Mapping[str, Any], conclusion: str, classification: InterpretationClassification | str, evidence: Any = None, registry: Mapping[str, Any] | None = None) -> InterpretationRecord:
    if registry is None or result_hash not in registry:
        raise InterpretationIntegrityError("registered result is required")
    _check_runtime(parameters)
    _check_runtime(analytical_target)
    _check_runtime(evidence)
    result = registry[result_hash]
    verifier = getattr(result, "verify", None)
    if callable(verifier) and not verifier():
        raise InterpretationIntegrityError("result integrity failed")
    try:
        classification = InterpretationClassification(classification)
    except ValueError as exc:
        raise InterpretationIntegrityError("invalid classification") from exc
    rec = InterpretationRecord(
        interpretation_hash="",
        result_hash=result_hash,
        analytical_target=_freeze(analytical_target),
        method=str(method),
        parameters=_freeze(parameters),
        conclusion=str(conclusion),
        classification=classification,
        evidence=_freeze(evidence),
        execution_hash=getattr(result, "execution_hash", None),
        question_hash=getattr(result, "question_hash", None),
        plan_hash=getattr(result, "plan_hash", None),
        trace_hash=getattr(result, "trace_hash", None),
        state_hash=getattr(result, "state_hash", None),
    )
    object.__setattr__(rec, "interpretation_hash", _hash(rec.canonical_payload()))
    rec.verify(registry)
    return rec
