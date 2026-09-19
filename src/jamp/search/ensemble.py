"""Search-domain policy ensemble for P15.1/P15.2/P15.3."""
from __future__ import annotations

from typing import List, Tuple

from .candidate import SearchCandidate, SearchResult
from .boundary import SearchPolicy
from .dedup import CandidateDeduplicator
from .feedback import SearchFeedback


class PolicyEnsemble:
    """Compose policies, deduplicate proposals, and broadcast immutable feedback."""

    def __init__(self, policies: Tuple[SearchPolicy, ...]):
        if not policies:
            raise ValueError("policies must contain at least one SearchPolicy")
        self._policies = tuple(policies)

    @property
    def name(self) -> str:
        return "ensemble[" + ",".join(policy.name for policy in self._policies) + "]"

    @property
    def policies(self) -> Tuple[SearchPolicy, ...]:
        return self._policies

    def propose(self, context_statement: str) -> List[SearchCandidate]:
        raw_proposals: List[SearchCandidate] = []
        for policy in self._policies:
            raw_proposals.extend(policy.propose(context_statement))
        return CandidateDeduplicator.deduplicate(raw_proposals)

    def receive_feedback(self, feedback: SearchFeedback) -> None:
        """Forward feedback only to policies exposing the optional feedback contract."""
        for policy in self._policies:
            receiver = getattr(policy, "receive_feedback", None)
            if receiver is not None:
                receiver(feedback)

    def search(self, context_statement: str) -> SearchResult:
        """Return the deduplicated ensemble output in SearchResult."""
        return SearchResult(
            candidates=tuple(self.propose(context_statement)),
            context_statement=context_statement,
            policy_name=self.name,
        )
