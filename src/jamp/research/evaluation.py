"""P22.4 deterministic, evidence-grounded evaluation.

The evaluator exposes raw empirical measurements only. It performs no
selection, ranking, thresholding, heuristic weighting, or environment access.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .canonical import replay_hash
from .search_space import SearchSpaceError, SearchState

__all__ = ("EvaluationMetrics", "evaluate_candidate")


@dataclass(frozen=True)
class EvaluationMetrics:
    state_hash: str
    evidence_root: str
    causal_root: str
    score: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(self, "score", MappingProxyType(dict(self.score)))


def evaluate_candidate(candidate: SearchState) -> EvaluationMetrics:
    """Measure a structurally validated candidate without making decisions."""
    if not isinstance(candidate, SearchState):
        raise TypeError("candidate must be a SearchState")

    exported = candidate.export()
    if replay_hash(exported) != candidate.state_hash:
        raise SearchSpaceError("candidate state_hash does not match canonical export")

    hypotheses = candidate.hypotheses
    metrics = {
        "claim_count": sum(len(h.claims) for h in hypotheses),
        "supporting_evidence_count": sum(len(h.support) for h in hypotheses),
        "contradicting_evidence_count": sum(len(h.contradicting) for h in hypotheses),
        "causal_dependency_count": sum(len(h.causal) for h in hypotheses),
        "assumption_count": len(candidate.assumptions),
        "admissible_intervention_count": sum(len(h.interventions) for h in hypotheses),
        "search_depth": candidate.depth,
    }
    return EvaluationMetrics(
        state_hash=candidate.state_hash,
        evidence_root=candidate.evidence_root,
        causal_root=candidate.causal_root,
        score=metrics,
    )
