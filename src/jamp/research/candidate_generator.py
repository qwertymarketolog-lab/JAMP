"""P22.2 deterministic candidate generation.

This module enumerates structurally admissible descendants of a SearchState.
It deliberately contains no ranking, scoring, selection, Bayesian weighting,
or counterfactual evaluation.
"""
from __future__ import annotations

from typing import Iterable

from .search_space import SearchSpaceError, SearchState, apply_mutation, MutationOp


def generate_candidate_states(state: SearchState) -> tuple[SearchState, ...]:
    """Return the canonical, evidence-compliant descendants of ``state``.

    Generation is a pure function: the input is verified but never mutated.
    Candidate order is determined solely by the resulting content hashes.
    """
    state.verify()
    if not state.hypothesis_set:
        return ()

    candidates: dict[str, SearchState] = {}
    for index, hypothesis in enumerate(state.hypothesis_set):
        for condition in hypothesis.claims:
            payload = {"condition": condition}
            try:
                candidate = apply_mutation(state, MutationOp.REMOVE_CONDITION, payload)
            except (SearchSpaceError, KeyError, TypeError, ValueError):
                continue
            candidates[candidate.state_hash] = candidate

        for assumption in hypothesis.assumptions:
            payload = {"assumption": assumption}
            try:
                candidate = apply_mutation(state, MutationOp.REMOVE_ASSUMPTION, payload)
            except (SearchSpaceError, KeyError, TypeError, ValueError):
                continue
            candidates[candidate.state_hash] = candidate

    return tuple(sorted(candidates.values(), key=lambda candidate: candidate.state_hash))


# Explicit public alias used by the P22.2 contract.
generate_candidates = generate_candidate_states


__all__ = ["generate_candidate_states", "generate_candidates"]
