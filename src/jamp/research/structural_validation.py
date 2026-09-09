"""P22.3 deterministic structural validation and constraint enforcement.

The validator checks immutable search-state structure, cryptographic identity,
lineage, inherited constraints, and hypothesis provenance. It has no heuristic
or external decision mechanism and does not mutate its inputs.
"""
from __future__ import annotations

from collections.abc import Iterable

from .search_space import SearchSpaceError, SearchState


def _raise(message: str) -> None:
    raise SearchSpaceError(message)


def _validate_one(parent: SearchState, candidate: SearchState) -> SearchState:
    if not isinstance(candidate, SearchState):
        _raise("candidate must be a SearchState")

    try:
        parent.verify()
        candidate.verify()
    except SearchSpaceError:
        raise

    if candidate is parent or candidate.state_hash == parent.state_hash:
        _raise("parent cannot be a candidate")
    if candidate.evidence_root != parent.evidence_root:
        _raise("evidence root lineage mismatch")
    if candidate.causal_root != parent.causal_root:
        _raise("causal root lineage mismatch")
    if candidate.search_depth != parent.search_depth + 1:
        _raise("candidate depth must advance exactly one")
    if candidate.constraints != parent.constraints:
        _raise("constraints must be preserved")
    if candidate.assumptions != parent.assumptions:
        _raise("state assumptions must be preserved")
    if len(candidate.hypothesis_set) != len(parent.hypothesis_set):
        _raise("hypothesis lineage must be preserved")

    for parent_hypothesis, candidate_hypothesis in zip(parent.hypothesis_set, candidate.hypothesis_set):
        if candidate_hypothesis.supporting_evidence != parent_hypothesis.supporting_evidence:
            _raise("supporting evidence must be preserved")
        if candidate_hypothesis.contradicting_evidence != parent_hypothesis.contradicting_evidence:
            _raise("contradicting evidence must be preserved")
        if candidate_hypothesis.assumptions != parent_hypothesis.assumptions:
            _raise("hypothesis assumptions must be preserved")
        if candidate_hypothesis.causal_dependencies != parent_hypothesis.causal_dependencies:
            _raise("causal dependencies must be preserved")
        if candidate_hypothesis.admissible_interventions != parent_hypothesis.admissible_interventions:
            _raise("admissible interventions must be preserved")

    return candidate


def validate_candidate(parent: SearchState, candidate: SearchState) -> SearchState:
    """Validate one candidate against its immutable parent state."""
    if not isinstance(parent, SearchState):
        _raise("parent must be a SearchState")
    return _validate_one(parent, candidate)


def validate_candidates(parent: SearchState, candidates: Iterable[SearchState]) -> tuple[SearchState, ...]:
    """Validate candidates and return them in canonical state-hash order."""
    if not isinstance(parent, SearchState):
        _raise("parent must be a SearchState")
    try:
        parent.verify()
    except SearchSpaceError:
        raise
    if not isinstance(candidates, Iterable):
        _raise("candidates must be iterable")

    unique: dict[str, SearchState] = {}
    for candidate in candidates:
        validated = _validate_one(parent, candidate)
        if validated.state_hash in unique:
            _raise("duplicate candidate")
        unique[validated.state_hash] = validated

    return tuple(sorted(unique.values(), key=lambda state: state.state_hash))


__all__ = ["validate_candidates", "validate_candidate"]
