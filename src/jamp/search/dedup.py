"""Deterministic Search Domain candidate canonicalization and deduplication."""

from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List

from .candidate import (
    CompositeSearchProvenance,
    SearchCandidate,
    SearchProvenance,
)


class CandidateDeduplicator:
    """Merge equivalent search hypotheses without crossing the State Domain."""

    @staticmethod
    def canonicalize_statement(statement: str) -> str:
        return statement.strip().lower()

    @classmethod
    def identity_key(cls, statement: str) -> str:
        return hashlib.sha256(
            cls.canonicalize_statement(statement).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _merge_provenance(
        provenances: List[SearchProvenance],
    ) -> CompositeSearchProvenance:
        primary_index, primary = max(
            enumerate(provenances), key=lambda item: (item[1].score, -item[0])
        )
        contributing = tuple(
            provenance
            for index, provenance in enumerate(provenances)
            if index != primary_index
        )
        sources = tuple(dict.fromkeys(provenance.policy_name for provenance in provenances))
        return CompositeSearchProvenance(
            primary_provenance=primary,
            contributing_provenances=contributing,
            sources=sources,
            aggregated_score=max(provenance.score for provenance in provenances),
        )

    @classmethod
    def deduplicate(cls, candidates: Iterable[SearchCandidate]) -> List[SearchCandidate]:
        grouped: Dict[str, List[SearchCandidate]] = {}
        order: List[str] = []
        for candidate in candidates:
            key = cls.identity_key(candidate.statement)
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(candidate)

        merged: List[SearchCandidate] = []
        for key in order:
            group = grouped[key]
            if len(group) == 1:
                merged.append(group[0])
                continue
            primary_index, primary = max(
                enumerate(group),
                key=lambda item: (item[1].provenance.score, -item[0]),
            )
            provenances = [candidate.provenance for candidate in group]
            if not all(isinstance(provenance, SearchProvenance) for provenance in provenances):
                raise TypeError("deduplication expects raw SearchProvenance inputs")
            merged.append(
                SearchCandidate(
                    candidate_id=primary.candidate_id,
                    statement=primary.statement,
                    source_id=primary.source_id,
                    provenance=cls._merge_provenance(provenances),
                )
            )
        return merged
