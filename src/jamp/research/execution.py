"""Deterministic empirical execution/result capture boundary for JAMP."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping


class ExecutionIntegrityError(ValueError):
    pass


_FORBIDDEN = {"timestamp", "uuid", "pid", "process_id", "hostname", "memory_address", "environment", "local_path"}


def _canon(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canon(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [_canon(x) for x in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported value: {type(value).__name__}")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _hash(value: Any) -> str:
    payload = json.dumps(_canon(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256(payload).hexdigest()


def _check_runtime_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN:
                raise ValueError(f"runtime metadata forbidden: {key}")
            _check_runtime_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_runtime_keys(child)


def _measurement_hash(obs: Mapping[str, Any]) -> str:
    metadata = obs.get("metadata", {})
    return _hash(metadata)


@dataclass(frozen=True)
class ExecutionRecord:
    plan_hash: str
    question_hash: str
    parameters: Mapping[str, Any]
    observations: tuple[Mapping[str, Any], ...]
    execution_hash: str
    result_hash: str
    observation_status: str
    trace_hash: str | None = None
    state_hash: str | None = None
    upstream_provenance: Mapping[str, Any] = MappingProxyType({})
    result_provenance: Mapping[str, Any] = MappingProxyType({})

    def compute_hash(self) -> str:
        return _hash({
            "plan_hash": self.plan_hash,
            "question_hash": self.question_hash,
            "parameters": self.parameters,
            "observations": self.observations,
            "trace_hash": self.trace_hash,
            "state_hash": self.state_hash,
        })

    def compute_result_hash(self) -> str:
        return _hash({
            "execution_hash": self.execution_hash,
            "observations": self.observations,
            "trace_hash": self.trace_hash,
            "state_hash": self.state_hash,
        })

    @property
    def provenance_chain(self) -> tuple[str, ...]:
        chain = (self.question_hash, self.plan_hash, self.execution_hash, self.result_hash)
        if self.trace_hash:
            chain += (self.trace_hash,)
        if self.state_hash:
            chain += (self.state_hash,)
        return chain

    def export(self) -> dict[str, Any]:
        return {
            "plan_hash": self.plan_hash,
            "question_hash": self.question_hash,
            "parameters": _thaw(self.parameters),
            "observations": _thaw(self.observations),
            "execution_hash": self.execution_hash,
            "result_hash": self.result_hash,
            "observation_status": self.observation_status,
            "trace_hash": self.trace_hash,
            "state_hash": self.state_hash,
            "upstream_provenance": _thaw(self.upstream_provenance),
            "result_provenance": _thaw(self.result_provenance),
        }

    def verify(self) -> bool:
        if self.compute_hash() != self.execution_hash:
            raise ExecutionIntegrityError("execution hash mismatch")
        if self.compute_result_hash() != self.result_hash:
            raise ExecutionIntegrityError("result hash mismatch")
        if not self.plan_hash or not self.question_hash:
            raise ExecutionIntegrityError("missing upstream binding")
        for obs in self.observations:
            if "interpretation" in obs or "claim" in obs:
                raise ExecutionIntegrityError("interpretation/claim cannot be captured as raw observation")
            if obs.get("measurement_metadata_hash") != _measurement_hash(obs):
                raise ExecutionIntegrityError("measurement metadata hash mismatch")
        if self.observation_status not in {"EMPTY", "CAPTURED"}:
            raise ExecutionIntegrityError("invalid observation status")
        if self.observation_status == "EMPTY" and self.observations:
            raise ExecutionIntegrityError("empty status with observations")
        if self.observation_status == "CAPTURED" and not self.observations:
            raise ExecutionIntegrityError("captured status without observations")
        if self.upstream_provenance:
            plans = self.upstream_provenance.get("plans", {})
            questions = self.upstream_provenance.get("questions", {})
            if self.plan_hash not in plans or self.question_hash not in questions:
                raise ExecutionIntegrityError("unknown upstream reference")
            plan = plans[self.plan_hash]
            question = questions[self.question_hash]
            if plan.get("plan_hash") != self.plan_hash or question.get("question_hash") != self.question_hash:
                raise ExecutionIntegrityError("upstream integrity mismatch")
            if plan.get("question_hash") not in (None, self.question_hash):
                raise ExecutionIntegrityError("plan/question substitution")
        return True


def make_execution(
    plan_hash: str,
    question_hash: str,
    parameters: Mapping[str, Any] | None,
    observations: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    *,
    registry: Mapping[str, Any] | None = None,
    trace_hash: str | None = None,
    state_hash: str | None = None,
) -> ExecutionRecord:
    if not plan_hash or not question_hash or parameters is None:
        raise ValueError("plan_hash, question_hash and parameters are required")
    _check_runtime_keys(parameters)
    _check_runtime_keys(observations)
    if trace_hash is not None and len(trace_hash) != 64:
        raise ValueError("invalid trace_hash")
    if state_hash is not None and len(state_hash) != 64:
        raise ValueError("invalid state_hash")

    frozen_obs = []
    for raw in observations:
        item = dict(raw)
        item.pop("interpretation", None)
        item.pop("claim", None)
        item["measurement_metadata_hash"] = _measurement_hash(item)
        frozen_obs.append(_freeze(item))
    frozen_parameters = _freeze(dict(parameters))
    upstream = MappingProxyType({})
    if registry is not None:
        plans = registry.get("plans", {})
        questions = registry.get("questions", {})
        if plan_hash not in plans or question_hash not in questions:
            # Keep construction possible for adversarial verification; verify() rejects it.
            upstream = MappingProxyType({"plans": _freeze(plans), "questions": _freeze(questions)})
        else:
            upstream = MappingProxyType({"plans": _freeze(plans), "questions": _freeze(questions)})
    temp = ExecutionRecord(
        plan_hash=plan_hash,
        question_hash=question_hash,
        parameters=frozen_parameters,
        observations=tuple(frozen_obs),
        execution_hash="",
        result_hash="",
        observation_status="EMPTY" if not frozen_obs else "CAPTURED",
        trace_hash=trace_hash,
        state_hash=state_hash,
        upstream_provenance=upstream,
        result_provenance=MappingProxyType({}),
    )
    execution_hash = temp.compute_hash()
    temp = ExecutionRecord(**{**temp.__dict__, "execution_hash": execution_hash})
    result_hash = temp.compute_result_hash()
    return ExecutionRecord(**{**temp.__dict__, "result_hash": result_hash, "result_provenance": MappingProxyType({"execution_hash": execution_hash})})
