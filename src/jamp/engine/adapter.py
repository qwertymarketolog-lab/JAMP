"""Explicit adapter from Search Domain values into JAMP candidates/feedback."""

from typing import List

from jamp.registry.candidates import Candidate, VerificationResult
from jamp.search.candidate import SearchCandidate, SearchResult
from jamp.search.feedback import SearchFeedback


def adapt_search_result_to_candidates(
    search_result: SearchResult,
) -> List[Candidate]:
    """Convert search proposals into canonical candidates at the engine boundary."""

    adapted: List[Candidate] = []
    for search_candidate in search_result.candidates:
        provenance = search_candidate.provenance
        adapted.append(
            Candidate(
                candidate_id=search_candidate.candidate_id,
                statement=search_candidate.statement,
                source_id=search_candidate.source_id,
                metadata={
                    "search_depth": provenance.depth,
                    "search_score": provenance.score,
                    "search_policy": provenance.policy_name,
                    "search_node_id": provenance.search_node_id,
                    **provenance.metadata,
                },
            )
        )
    return adapted


def emit_search_feedback(
    search_candidate: SearchCandidate,
    evaluation_result: VerificationResult,
    timestamp: float,
) -> SearchFeedback:
    """Translate a State Domain verdict into an immutable Search Domain value."""
    return SearchFeedback.from_evaluation(
        search_candidate,
        evaluation_result,
        timestamp=timestamp,
    )
