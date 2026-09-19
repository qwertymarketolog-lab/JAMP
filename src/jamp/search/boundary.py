"""Search Domain boundary for heuristic proposal policies and feedback."""

from typing import List, Protocol

from jamp.search.candidate import SearchCandidate, SearchResult
from jamp.search.feedback import SearchFeedback


class SearchPolicy(Protocol):
    """Minimal contract implemented by search proposal policies."""

    @property
    def name(self) -> str:
        ...

    def propose(self, context_statement: str) -> List[SearchCandidate]:
        ...


class FeedbackAwareSearchPolicy(SearchPolicy, Protocol):
    """Optional policy contract for receiving immutable verification feedback."""

    def receive_feedback(self, feedback: SearchFeedback) -> None:
        ...


class SearchBoundary:
    """Sandboxed search facade for proposals and immutable feedback."""

    def __init__(self, policy: SearchPolicy):
        self._policy = policy

    def expand_and_propose(self, context_statement: str) -> SearchResult:
        proposals = self._policy.propose(context_statement)
        return SearchResult(
            candidates=tuple(proposals),
            context_statement=context_statement,
            policy_name=self._policy.name,
        )

    def submit_feedback(self, feedback: SearchFeedback) -> None:
        """Deliver value-only feedback to a policy that explicitly accepts it."""
        receiver = getattr(self._policy, "receive_feedback", None)
        if receiver is not None:
            receiver(feedback)
