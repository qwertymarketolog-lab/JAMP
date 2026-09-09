"""P22.2 deterministic candidate generation.

This module enumerates structurally admissible descendants of a SearchState.
It deliberately contains no ranking, scoring, selection, Bayesian weighting,
or counterfactual evaluation.
"""
from __future__ import annotations

from .search_space import SearchSpaceError, SearchState, apply_mutation, MutationOp


def generate_candidate_states(state: SearchState) -> tuple[SearchState, ...]:
    """Return canonical, evidence-compliant descendants of ``state``.

    Generation is pure: the input is verified but never mutated. The P22.2
    contract requires hypothesis assumptions, evidence, causal dependencies,
    and interventions to remain inherited unchanged, so generation does not
    remove assumptions. Candidate order is determined solely by state hashes.
    """
    state.verify()
    if not state.hypothesis_set:
        return ()

    if any(c.startswith("depth<=") for c in state.constraints):
        limit = int(next(c.split("<=", 1)[1] for c in state.constraints if c.startswith("depth<=")))
        if state.search_depth >= limit:
            return ()

    candidates: dict[str, SearchState] = {}
    for hypothesis in state.hypothesis_set:
        for condition in hypothesis.claims:
            try:
                candidate = apply_mutation(
                    state,
                    MutationOp.REMOVE_CONDITION,
                    {"condition": condition},
                )
            except (SearchSpaceError, KeyError, TypeError, ValueError):
                continue
            candidates[candidate.state_hash] = candidate

    return tuple(sorted(candidates.values(), key=lambda candidate: candidate.state_hash))


# Explicit public alias used by the P22.2 contract.
generate_candidates = generate_candidate_states


__all__ = ["generate_candidate_states", "generate_candidates"]
