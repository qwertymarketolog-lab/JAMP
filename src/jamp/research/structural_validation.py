"""P22.3 structural validation and constraint enforcement.

The validator is a pure, deterministic structural gate. It validates candidate
states without generating, ranking, scoring, selecting, or evaluating
counterfactuals. Validation checks candidate and parent state identity,
cryptographic hash integrity, evidence roots, causal dependencies, assumptions,
lineage, structural constraints, duplicates, and canonical ordering.
External state, randomness, time, and network access are not consulted, and
inputs are never mutated.
"""
from __future__ import annotations

from typing import Iterable

from .canonical import replay_hash
from .search_space import SearchSpaceError, SearchState


class StructuralValidationError(ValueError):
    """Raised when a P22.3 structural constraint is violated."""


def _validate_one(parent: SearchState, candidate: SearchState) -> None:
    if not isinstance(candidate, SearchState):
        raise StructuralValidationError("invalid candidate structure")
    parent.verify()
    candidate.verify()
    if candidate.evidence_root != parent.evidence_root:
        raise StructuralValidationError("evidence lineage mismatch")
    if candidate.causal_root != parent.causal_root:
        raise StructuralValidationError("causal lineage mismatch")
    if candidate.search_depth != parent.search_depth + 1:
        raise StructuralValidationError("invalid candidate state depth")
    if candidate.assumptions != parent.assumptions:
        raise StructuralValidationError("state assumptions were not preserved")
    if len(candidate.hypothesis_set) != len(parent.hypothesis_set):
        raise StructuralValidationError("hypothesis lineage mismatch")
    parent_by_hash = {h.hypothesis_hash: h for h in parent.hypothesis_set}
    for hypothesis in candidate.hypothesis_set:
        for digest in hypothesis.supporting_evidence + hypothesis.contradicting_evidence + hypothesis.causal_dependencies:
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise StructuralValidationError("invalid evidence/causal hash")
        if hypothesis.causal_dependencies and not set(hypothesis.causal_dependencies).issubset({parent.causal_root}):
            raise StructuralValidationError("causal dependency escaped parent root")
        matching = parent_by_hash.get(hypothesis.hypothesis_hash)
        if matching is None:
            if not any(h.claims == hypothesis.claims or h.assumptions == hypothesis.assumptions for h in parent.hypothesis_set):
                raise StructuralValidationError("candidate hypothesis has no parent lineage")


def validate_candidates(parent: SearchState, candidates: Iterable[SearchState]) -> tuple[SearchState, ...]:
    """Return an ordered validation result for structurally valid candidates.

    This pure P22.3 validator rejects invalid structures, duplicate candidates,
    broken lineage, changed assumptions, invalid evidence roots, causal
    dependency violations, hash failures, and state/depth constraint failures.
    Results use canonical hash order. The validator never mutates inputs,
    generates candidates, selects candidates, scores candidates, ranks
    candidates, or evaluates counterfactuals. It uses no heuristic, no
    external ranking, no Bayesian weighting, and no counterfactual scoring;
    there is no external state, randomness, time, or network dependency.
    """
    if not isinstance(parent, SearchState):
        raise StructuralValidationError("invalid parent state")
    parent.verify()
    if not isinstance(candidates, Iterable):
        raise StructuralValidationError("candidates must be iterable")

    unique: dict[str, SearchState] = {}
    for candidate in candidates:
        _validate_one(parent, candidate)
        digest = candidate.state_hash
        if digest in unique:
            raise StructuralValidationError("duplicate candidate")
        unique[digest] = candidate

    ordered = tuple(sorted(unique.values(), key=lambda state: state.state_hash))
    if tuple(state.state_hash for state in ordered) != tuple(sorted(unique)):
        raise StructuralValidationError("non-canonical candidate order")
    return ordered


__all__ = ["StructuralValidationError", "validate_candidates"]
