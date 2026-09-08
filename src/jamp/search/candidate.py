"""Immutable value objects exchanged inside the JAMP Search Domain."""

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Union


@dataclass(frozen=True)
class SearchProvenance:
    """Metadata describing where and how a search proposal was produced."""

    search_node_id: str
    depth: int
    score: float
    policy_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompositeSearchProvenance:
    """Complete provenance for one hypothesis proposed by multiple policies."""

    primary_provenance: SearchProvenance
    contributing_provenances: Tuple[SearchProvenance, ...]
    sources: Tuple[str, ...]
    aggregated_score: float

    @property
    def search_node_id(self) -> str:
        return self.primary_provenance.search_node_id

    @property
    def depth(self) -> int:
        return self.primary_provenance.depth

    @property
    def score(self) -> float:
        return self.aggregated_score

    @property
    def policy_name(self) -> str:
        return self.primary_provenance.policy_name

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            **self.primary_provenance.metadata,
            "provenance_sources": self.sources,
            "provenance_count": len(self.sources),
            "aggregated_score": self.aggregated_score,
            "contributing_search_node_ids": tuple(
                provenance.search_node_id for provenance in self.contributing_provenances
            ),
        }


@dataclass(frozen=True)
class SearchCandidate:
    """A search-domain proposal that has not entered JAMP state."""

    candidate_id: str
    statement: str
    source_id: str
    provenance: Union[SearchProvenance, CompositeSearchProvenance]


@dataclass(frozen=True)
class SearchResult:
    """Immutable result returned by a search policy through the boundary."""

    candidates: Tuple[SearchCandidate, ...]
    context_statement: str
    policy_name: str
