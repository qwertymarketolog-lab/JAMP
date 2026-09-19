"""Immutable feedback values exchanged across the JAMP search boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FeedbackStatus(Enum):
    """Search-domain interpretation of a verification verdict."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SearchFeedback:
    """Immutable verification feedback with no reference to JAMP state."""

    search_node_id: str
    status: FeedbackStatus
    reason: str | None
    evaluator_id: str
    timestamp: float

    @classmethod
    def from_evaluation(
        cls,
        search_candidate: Any,
        evaluation_result: Any,
        timestamp: float,
    ) -> "SearchFeedback":
        """Create feedback from evaluation-shaped values without importing State Domain types.

        The timestamp is supplied by the caller so replay/tests remain deterministic.
        """
        status_name = getattr(getattr(evaluation_result, "status"), "value", None)
        if status_name is None:
            status_name = str(evaluation_result.status)
        mapping = {
            "CONFIRMED": FeedbackStatus.ACCEPTED,
            "ACCEPTED": FeedbackStatus.ACCEPTED,
            "REJECTED": FeedbackStatus.REJECTED,
            "CONFLICT": FeedbackStatus.REJECTED,
            "UNKNOWN": FeedbackStatus.UNKNOWN,
        }
        try:
            status = mapping[status_name]
        except KeyError as exc:
            raise ValueError(f"unsupported evaluation status: {status_name}") from exc

        provenance = getattr(search_candidate, "provenance", None)
        search_node_id = getattr(provenance, "search_node_id", None)
        if search_node_id is None:
            metadata = getattr(search_candidate, "metadata", {})
            search_node_id = metadata.get("search_node_id")
        if not search_node_id:
            raise ValueError("search candidate has no search_node_id")

        evaluation_provenance = getattr(evaluation_result, "provenance", None)
        evaluator_id = getattr(evaluation_provenance, "rule_applied", None)
        if not evaluator_id:
            evaluator_id = type(evaluation_result).__name__

        reason = None if status is FeedbackStatus.ACCEPTED else status.value
        return cls(
            search_node_id=search_node_id,
            status=status,
            reason=reason,
            evaluator_id=evaluator_id,
            timestamp=timestamp,
        )
