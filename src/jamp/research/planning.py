"""P20.7 deterministic research planning and experiment-selection engine.

This module is deliberately research-only. It converts verified question states and
registered evidence into immutable candidate experiment designs. It never predicts
or asserts an empirical result.
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
_RUNTIME_KEYS = frozenset({"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"})
_FORBIDDEN_FACT_WORDS = ("proves", "proved", "will yield", "yields", "definitely", "certainly", "is true", "is false")


class PlanningError(ValueError):
    """Invalid or unverifiable planning input."""


class PlanningIntegrityError(PlanningError):
    """Content-address or provenance integrity failure."""


class PlanningStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    SELECTED = "SELECTED"
    BLOCKED = "BLOCKED"
    EXECUTED = "EXECUTED"


class PlanningStrategy(str, Enum):
    GAP = "GAP"
    DISCRIMINATE = "DISCRIMINATE"
    UNCERTAINTY_REDUCTION = "UNCERTAINTY_REDUCTION"
    INFORMATION_ACQUISITION = "INFORMATION_ACQUISITION"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value):
            raise PlanningIntegrityError("runtime metadata is forbidden")
        if any(not isinstance(k, str) for k in value):
            raise PlanningIntegrityError("mapping keys must be strings")
        return MappingProxyType({k: _freeze(value[k]) for k in sorted(value)})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(x) for x in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze(x) for x in value), key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _canonical_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanningIntegrityError(f"{name} must be non-empty")
    return " ".join(value.split())


def _ref_tuple(values: Sequence[str], name: str) -> tuple[str, ...]:
    out = tuple(dict.fromkeys(values))
    if any(not isinstance(x, str) or not x.strip() for x in out):
        raise PlanningIntegrityError(f"{name} contains invalid reference")
    return out


def compute_plan_hash(
    payload_or_objective: Mapping[str, Any] | str,
    strategy: str | PlanningStrategy | None = None,
    question_refs: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    conditions: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """Compute the plan identity from semantic planning content only."""
    if isinstance(payload_or_objective, Mapping):
        p = dict(payload_or_objective)
        p.pop("plan_hash", None)
        material = {
            k: _thaw(_freeze(v)) for k, v in p.items()
            if k not in _RUNTIME_KEYS and k != "provenance"
        }
    else:
        s = strategy.value if isinstance(strategy, PlanningStrategy) else strategy
        material = {
            "objective": _canonical_text(payload_or_objective, "objective"),
            "strategy": s,
            "question_refs": list(dict.fromkeys(question_refs)),
            "evidence_refs": list(dict.fromkeys(evidence_refs)),
            "conditions": _thaw(_freeze(conditions or {})),
            **{k: _thaw(_freeze(v)) for k, v in kwargs.items() if k not in _RUNTIME_KEYS},
        }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _registry_contains(registry: Any, ref: str, kind: str) -> bool:
    if isinstance(registry, Mapping):
        bucket = registry.get(kind, {})
        return ref in bucket
    if kind == "evidence" and hasattr(registry, "contains"):
        return bool(registry.contains(ref))
    return False


def _registry_get(registry: Any, ref: str, kind: str) -> Any:
    if isinstance(registry, Mapping):
        return registry[kind][ref]
    if kind == "evidence" and hasattr(registry, "get"):
        return registry.get(ref)
    raise PlanningIntegrityError(f"unregistered {kind}: {ref}")


def _verify_evidence(registry: Any, ref: str) -> Mapping[str, Any]:
    if not _registry_contains(registry, ref, "evidence"):
        raise PlanningIntegrityError("unknown evidence reference")
    item = _registry_get(registry, ref, "evidence")
    if hasattr(item, "verify_integrity") and not item.verify_integrity():
        raise PlanningIntegrityError("evidence integrity failure")
    if isinstance(item, Mapping):
        if item.get("result_hash", ref) != ref:
            raise PlanningIntegrityError("evidence identity substitution")
        return item
    if getattr(item, "result_hash", ref) != ref:
        raise PlanningIntegrityError("evidence identity substitution")
    return MappingProxyType({
        "result_hash": getattr(item, "result_hash", ref),
        "trace_hash": getattr(item, "trace_hash", None),
        "event_ids": tuple(getattr(item, "event_ids", ())),
        "state_anchors": tuple(getattr(item, "state_anchors", ())),
    })


def _verify_claim(registry: Any, ref: str) -> None:
    if not _registry_contains(registry, ref, "claims"):
        raise PlanningIntegrityError("unknown claim reference")
    claim = _registry_get(registry, ref, "claims")
    if isinstance(claim, Mapping):
        if claim.get("claim_hash", ref) != ref:
            raise PlanningIntegrityError("claim identity substitution")
        return
    if getattr(claim, "claim_hash", ref) != ref:
        raise PlanningIntegrityError("claim identity substitution")
    verify = getattr(claim, "verify", None)
    if callable(verify):
        try:
            verify(registry)
        except Exception as exc:
            raise PlanningIntegrityError("claim integrity failure") from exc


def _question(registry: Any, ref: str) -> Mapping[str, Any]:
    if not _registry_contains(registry, ref, "questions"):
        raise PlanningIntegrityError("unknown question reference")
    q = _registry_get(registry, ref, "questions")
    if isinstance(q, Mapping):
        if q.get("question_hash", ref) != ref:
            raise PlanningIntegrityError("question identity substitution")
        return q
    if getattr(q, "question_hash", ref) != ref:
        raise PlanningIntegrityError("question identity substitution")
    if hasattr(q, "verify"):
        try:
            q.verify(registry=registry)
        except Exception as exc:
            raise PlanningIntegrityError("question integrity failure") from exc
    return MappingProxyType({
        "question_hash": ref,
        "status": getattr(q, "status", "UNRESOLVED").value if isinstance(getattr(q, "status", None), Enum) else getattr(q, "status", "UNRESOLVED"),
        "formulation": getattr(q, "formulation", ""),
        "provenance": getattr(q, "provenance", {}),
    })


def _forbidden_outcome(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    low = value.lower()
    return any(term in low for term in _FORBIDDEN_FACT_WORDS)


@dataclass(frozen=True, slots=True)
class ResearchPlan:
    objective: str
    strategy: PlanningStrategy
    status: PlanningStatus
    question_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    conditions: Mapping[str, Any]
    experiment_objective: str
    candidate_outcomes: tuple[str, ...]
    hypothesis_refs: tuple[str, ...]
    selection_rationale: Mapping[str, Any]
    candidate_experiment: Mapping[str, Any]
    provenance: Mapping[str, Any]
    plan_hash: str

    def __post_init__(self) -> None:
        objective = _canonical_text(self.objective, "objective")
        strategy = self.strategy if isinstance(self.strategy, PlanningStrategy) else PlanningStrategy(self.strategy)
        status = self.status if isinstance(self.status, PlanningStatus) else PlanningStatus(self.status)
        questions = _ref_tuple(self.question_refs, "question_refs")
        evidence = _ref_tuple(self.evidence_refs, "evidence_refs")
        hypotheses = _ref_tuple(self.hypothesis_refs, "hypothesis_refs")
        conditions = _freeze(self.conditions)
        rationale = _freeze(self.selection_rationale)
        experiment_objective = _canonical_text(self.experiment_objective, "experiment_objective")
        outcomes = tuple(_canonical_text(x, "candidate_outcome") for x in self.candidate_outcomes)
        if not outcomes:
            raise PlanningIntegrityError("candidate outcomes are required")
        if any(_forbidden_outcome(x) for x in outcomes):
            raise PlanningIntegrityError("empirical facts cannot be asserted as outcomes")
        provenance = _freeze(self.provenance)
        expected = compute_plan_hash({
            "objective": objective, "strategy": strategy.value, "status": status.value,
            "question_refs": questions, "evidence_refs": evidence, "conditions": conditions,
            "experiment_objective": experiment_objective, "candidate_outcomes": outcomes,
            "hypothesis_refs": hypotheses, "selection_rationale": rationale,
            "candidate_experiment": self.candidate_experiment,
        })
        if expected != self.plan_hash:
            raise PlanningIntegrityError("plan_hash does not match content")
        object.__setattr__(self, "objective", objective)
        object.__setattr__(self, "strategy", strategy)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "question_refs", questions)
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "hypothesis_refs", hypotheses)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "experiment_objective", experiment_objective)
        object.__setattr__(self, "candidate_outcomes", outcomes)
        object.__setattr__(self, "selection_rationale", rationale)
        object.__setattr__(self, "candidate_experiment", _freeze(self.candidate_experiment))
        object.__setattr__(self, "provenance", provenance)

    def verify(self, *, registry: Any | None = None) -> bool:
        if registry is not None:
            for ref in self.question_refs:
                _question(registry, ref)
            for ref in self.evidence_refs:
                _verify_evidence(registry, ref)
            for ref in self.selection_rationale.get("claim_refs", ()):
                _verify_claim(registry, ref)
        expected = compute_plan_hash(self.export())
        if expected != self.plan_hash:
            raise PlanningIntegrityError("plan integrity failure")
        return True

    def export(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "objective": self.objective, "strategy": self.strategy.value, "status": self.status.value,
            "question_refs": self.question_refs, "evidence_refs": self.evidence_refs,
            "conditions": _thaw(self.conditions), "experiment_objective": self.experiment_objective,
            "candidate_outcomes": self.candidate_outcomes, "hypothesis_refs": self.hypothesis_refs,
            "selection_rationale": _thaw(self.selection_rationale),
            "candidate_experiment": _thaw(self.candidate_experiment),
            "provenance": _thaw(self.provenance), "plan_hash": self.plan_hash,
        })


def make_plan(
    registry: Any,
    *,
    objective: str,
    strategy: str | PlanningStrategy,
    status: str | PlanningStatus,
    question_refs: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
    conditions: Mapping[str, Any] | None = None,
    experiment_objective: str | None = None,
    candidate_outcomes: Sequence[str] = (),
    hypothesis_refs: Sequence[str] = (),
    selection_rationale: Mapping[str, Any] | None = None,
    runtime_metadata: Mapping[str, Any] | None = None,
) -> ResearchPlan:
    if runtime_metadata:
        raise PlanningIntegrityError("runtime metadata is forbidden")
    objective = _canonical_text(objective, "objective")
    strategy = strategy.value if isinstance(strategy, PlanningStrategy) else strategy
    status = status.value if isinstance(status, PlanningStatus) else status
    try:
        strategy_enum = PlanningStrategy(strategy)
        status_enum = PlanningStatus(status)
    except ValueError as exc:
        raise PlanningIntegrityError("invalid strategy or status") from exc
    questions = _ref_tuple(question_refs, "question_refs")
    evidence = _ref_tuple(evidence_refs, "evidence_refs")
    hypotheses = _ref_tuple(hypothesis_refs, "hypothesis_refs")
    qrecords = [_question(registry, ref) for ref in questions]
    for ref in evidence:
        _verify_evidence(registry, ref)
    for h in hypotheses:
        # Hypothesis records may be exposed by a registry-like mapping.
        if isinstance(registry, Mapping) and h in registry.get("hypotheses", {}):
            item = registry["hypotheses"][h]
            if isinstance(item, Mapping) and item.get("hypothesis_hash", h) != h:
                raise PlanningIntegrityError("hypothesis substitution")
        elif isinstance(registry, Mapping) and registry.get("hypotheses") is not None:
            raise PlanningIntegrityError("unknown hypothesis reference")
    qstatuses = []
    for q in qrecords:
        value = q.get("status", "UNRESOLVED") if isinstance(q, Mapping) else "UNRESOLVED"
        if isinstance(value, Enum):
            value = value.value
        qstatuses.append(value)
    if "ANSWERED" in qstatuses and strategy_enum != PlanningStrategy.INFORMATION_ACQUISITION:
        raise PlanningError("answered question cannot silently require an experiment")
    purpose = {
        PlanningStrategy.GAP: "information_acquisition",
        PlanningStrategy.INFORMATION_ACQUISITION: "information_acquisition",
        PlanningStrategy.DISCRIMINATE: "discrimination",
        PlanningStrategy.UNCERTAINTY_REDUCTION: "uncertainty_reduction",
    }[strategy_enum]
    exp_obj = _canonical_text(experiment_objective or objective, "experiment_objective")
    outcomes = tuple(candidate_outcomes) or ("empirical trace consistent with one or more candidate explanations",)
    if any(_forbidden_outcome(x) for x in outcomes):
        raise PlanningIntegrityError("empirical facts cannot be asserted")
    rationale = dict(selection_rationale or {"basis": "deterministic strategy/question mapping", "question_refs": list(questions)})
    if "claim_refs" in rationale:
        for ref in rationale["claim_refs"]:
            _verify_claim(registry, ref)
    candidate = {
        "purpose": purpose,
        "question_hash": questions[0] if questions else None,
        "parameters": _thaw(_freeze(conditions or {})),
        "observable_outcomes": list(outcomes),
        "outcome_status": "UNKNOWN_UNTIL_EXECUTED",
    }
    provenance = {
        "question_refs": questions,
        "evidence_refs": evidence,
        "hypothesis_refs": hypotheses,
        "recursive_sources": [q.get("provenance", {}) for q in qrecords if isinstance(q, Mapping)],
    }
    material = {
        "objective": objective, "strategy": strategy_enum.value, "status": status_enum.value,
        "question_refs": questions, "evidence_refs": evidence, "conditions": conditions or {},
        "experiment_objective": exp_obj, "candidate_outcomes": outcomes, "hypothesis_refs": hypotheses,
        "selection_rationale": rationale, "candidate_experiment": candidate,
    }
    plan_hash = compute_plan_hash(material)
    return ResearchPlan(
        objective=objective, strategy=strategy_enum, status=status_enum,
        question_refs=questions, evidence_refs=evidence, conditions=conditions or {},
        experiment_objective=exp_obj, candidate_outcomes=outcomes, hypothesis_refs=hypotheses,
        selection_rationale=rationale, candidate_experiment=candidate,
        provenance=provenance, plan_hash=plan_hash,
    )
