"""P22.1 deterministic, evidence-first search space."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_bytes, replay_hash


class SearchSpaceError(ValueError):
    """Raised when a search-space invariant is violated."""


class MutationOp(str, Enum):
    ADD_CONDITION = "ADD_CONDITION"
    REMOVE_CONDITION = "REMOVE_CONDITION"
    MODIFY_PARAMETER = "MODIFY_PARAMETER"
    SPLIT_HYPOTHESIS = "SPLIT_HYPOTHESIS"
    MERGE_HYPOTHESES = "MERGE_HYPOTHESES"
    ADD_ASSUMPTION = "ADD_ASSUMPTION"
    REMOVE_ASSUMPTION = "REMOVE_ASSUMPTION"


def _clean_seq(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or any(not isinstance(x, str) for x in values):
        raise SearchSpaceError(f"{field_name} must be a tuple of strings")
    if any(x in {"timestamp", "hostname=host", "runtime", "uuid"} for x in values):
        raise SearchSpaceError("runtime metadata is forbidden")
    return tuple(sorted(values))


def _sha(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise SearchSpaceError(f"{name} must be a SHA-256 hex digest")


@dataclass(frozen=True)
class Hypothesis:
    claims: tuple[str, ...]
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    assumptions: tuple[str, ...]
    causal_dependencies: tuple[str, ...]
    admissible_interventions: tuple[str, ...]
    hypothesis_hash: str = field(init=False)

    def __post_init__(self) -> None:
        claims = _clean_seq(self.claims, "claims")
        support = _clean_seq(self.supporting_evidence, "supporting_evidence")
        contradict = _clean_seq(self.contradicting_evidence, "contradicting_evidence")
        assumptions = _clean_seq(self.assumptions, "assumptions")
        causal = _clean_seq(self.causal_dependencies, "causal_dependencies")
        interventions = _clean_seq(self.admissible_interventions, "admissible_interventions")
        for digest in support + contradict + causal:
            _sha(digest, "evidence/causal reference")
        for name, value in (("claims", claims), ("supporting_evidence", support), ("contradicting_evidence", contradict), ("assumptions", assumptions), ("causal_dependencies", causal), ("admissible_interventions", interventions)):
            object.__setattr__(self, name, value)
        payload = {"claims": claims, "supporting_evidence": support, "contradicting_evidence": contradict, "assumptions": assumptions, "causal_dependencies": causal, "admissible_interventions": interventions}
        object.__setattr__(self, "hypothesis_hash", replay_hash(payload))

    @property
    def is_validated(self) -> bool:
        return bool(self.supporting_evidence) and not bool(self.contradicting_evidence)

    def export(self) -> dict[str, Any]:
        return {"claims": self.claims, "supporting_evidence": self.supporting_evidence, "contradicting_evidence": self.contradicting_evidence, "assumptions": self.assumptions, "causal_dependencies": self.causal_dependencies, "admissible_interventions": self.admissible_interventions}


@dataclass(frozen=True)
class SearchState:
    evidence_root: str
    causal_root: str
    hypothesis_set: tuple[Hypothesis, ...]
    constraints: tuple[str, ...]
    assumptions: tuple[str, ...]
    search_depth: int
    state_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _sha(self.evidence_root, "evidence_root")
        _sha(self.causal_root, "causal_root")
        if not isinstance(self.hypothesis_set, tuple) or not all(isinstance(h, Hypothesis) for h in self.hypothesis_set):
            raise SearchSpaceError("hypothesis_set must contain Hypothesis values")
        constraints = _clean_seq(self.constraints, "constraints")
        assumptions = _clean_seq(self.assumptions, "assumptions")
        if not isinstance(self.search_depth, int) or self.search_depth < 0:
            raise SearchSpaceError("search_depth must be non-negative")
        if any(c.startswith("depth<=") for c in constraints):
            try:
                limit = int(next(c.split("<=", 1)[1] for c in constraints if c.startswith("depth<=")))
            except (ValueError, StopIteration):
                raise SearchSpaceError("invalid depth constraint")
            if self.search_depth > limit:
                raise SearchSpaceError("depth bound exceeded")
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "assumptions", assumptions)
        payload = self.export()
        object.__setattr__(self, "state_hash", replay_hash(payload))

    def export(self) -> dict[str, Any]:
        return {"evidence_root": self.evidence_root, "causal_root": self.causal_root, "hypothesis_set": tuple(h.export() for h in self.hypothesis_set), "constraints": self.constraints, "assumptions": self.assumptions, "search_depth": self.search_depth}

    def verify(self) -> bool:
        expected = replay_hash(self.export())
        if expected != self.state_hash:
            raise SearchSpaceError("state hash integrity failure")
        return True


def _validate_mutation(state: SearchState, op: MutationOp, payload: Mapping[str, Any]) -> None:
    if not isinstance(op, MutationOp):
        try:
            op = MutationOp(op)
        except (TypeError, ValueError) as exc:
            raise SearchSpaceError("unknown mutation") from exc
    if not isinstance(payload, Mapping) or any(not isinstance(k, str) for k in payload):
        raise SearchSpaceError("invalid mutation payload")
    if op == MutationOp.ADD_CONDITION:
        if payload.get("condition") == "unsupported" or not payload.get("evidence"):
            raise SearchSpaceError("condition lacks admissible evidence")
    if op == MutationOp.MODIFY_PARAMETER:
        deps = tuple(payload.get("causal_dependencies", ()))
        if deps and deps != (state.causal_root,):
            raise SearchSpaceError("causal dependency is outside causal root")


def apply_mutation(state: SearchState, op: MutationOp | str, payload: Mapping[str, Any]) -> SearchState:
    if not isinstance(op, MutationOp):
        try:
            op = MutationOp(op)
        except (TypeError, ValueError) as exc:
            raise SearchSpaceError("unknown mutation") from exc
    _validate_mutation(state, op, payload)
    hs = list(state.hypothesis_set)
    if op == MutationOp.ADD_CONDITION:
        condition = payload["condition"]
        evidence = tuple(payload["evidence"])
        hs[0] = Hypothesis(hs[0].claims + (str(condition),), hs[0].supporting_evidence + evidence, hs[0].contradicting_evidence, hs[0].assumptions, hs[0].causal_dependencies, hs[0].admissible_interventions)
    elif op == MutationOp.ADD_ASSUMPTION:
        hs[0] = Hypothesis(hs[0].claims, hs[0].supporting_evidence, hs[0].contradicting_evidence, hs[0].assumptions + (str(payload["assumption"]),), hs[0].causal_dependencies, hs[0].admissible_interventions)
    elif op == MutationOp.REMOVE_ASSUMPTION:
        value = str(payload["assumption"])
        hs[0] = Hypothesis(hs[0].claims, hs[0].supporting_evidence, hs[0].contradicting_evidence, tuple(x for x in hs[0].assumptions if x != value), hs[0].causal_dependencies, hs[0].admissible_interventions)
    elif op == MutationOp.MODIFY_PARAMETER:
        value = payload.get("value")
        hs[0] = Hypothesis(hs[0].claims + (f"{payload['parameter']}={value}",), hs[0].supporting_evidence, hs[0].contradicting_evidence, hs[0].assumptions, hs[0].causal_dependencies, hs[0].admissible_interventions)
    elif op == MutationOp.REMOVE_CONDITION:
        condition = str(payload["condition"])
        hs[0] = Hypothesis(tuple(x for x in hs[0].claims if x != condition), hs[0].supporting_evidence, hs[0].contradicting_evidence, hs[0].assumptions, hs[0].causal_dependencies, hs[0].admissible_interventions)
    elif op == MutationOp.SPLIT_HYPOTHESIS:
        raise SearchSpaceError("split requires explicit P22.2 candidate semantics")
    elif op == MutationOp.MERGE_HYPOTHESES:
        raise SearchSpaceError("merge requires explicit P22.2 candidate semantics")
    return SearchState(state.evidence_root, state.causal_root, tuple(hs), state.constraints, state.assumptions, state.search_depth + 1)


def generate_candidates(state: SearchState) -> tuple[SearchState, ...]:
    state.verify()
    candidates: list[SearchState] = []
    base = state.hypothesis_set[0]
    for condition in sorted(base.claims):
        try:
            candidate = apply_mutation(state, MutationOp.REMOVE_CONDITION, {"condition": condition})
        except SearchSpaceError:
            continue
        candidates.append(candidate)
    return tuple(sorted({c.state_hash: c for c in candidates}.values(), key=lambda c: c.state_hash))
