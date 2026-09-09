"""P22.9 deterministic structural hypothesis support scoring.

The score is a reproducible support measure derived only from validated
hypothesis, evidence-ledger, and lineage-graph state. It is not a probability
of truth and performs no ranking or global normalization.
"""
from __future__ import annotations

from . import canonical
from .evidence import EvidenceLedger, verify_evidence
from .hypothesis_formation import Hypothesis, HypothesisSet, verify_hypothesis_provenance
from .lineage_graph import LineageGraph, verify_lineage

__all__ = ("score_hypothesis",)


def _validate_inputs(
    hypothesis: Hypothesis, ledger: EvidenceLedger, graph: LineageGraph
) -> None:
    if not isinstance(hypothesis, Hypothesis):
        raise TypeError("hypothesis must be a Hypothesis")
    if not isinstance(ledger, EvidenceLedger):
        raise TypeError("ledger must be an EvidenceLedger")
    if not isinstance(graph, LineageGraph):
        raise TypeError("graph must be a LineageGraph")


def score_hypothesis(
    hypothesis: Hypothesis, ledger: EvidenceLedger, graph: LineageGraph
) -> float:
    """Return the deterministic P22.9 structural support score.

    For n unique evidence references and u distinct source identities:

        D = n / (n + 1)
        I = u / n
        C = 1
        F = (D + I + C) / 3

    Invalid provenance is rejected rather than converted into positive
    support. The function is read-only and does not inspect global state.
    """
    _validate_inputs(hypothesis, ledger, graph)

    if not ledger.records:
        return 0.0

    if len(hypothesis.evidence_refs) != len(set(hypothesis.evidence_refs)):
        raise ValueError("duplicate evidence references are not permitted")

    verify_evidence(ledger, target_state_hash=hypothesis.state_hash)
    hypothesis_set = HypothesisSet(
        (hypothesis,), canonical.replay_hash([hypothesis.hypothesis_hash])
    )
    verify_hypothesis_provenance(hypothesis_set, ledger)
    verify_lineage(graph)

    evidence_by_hash = {record.evidence_hash: record for record in ledger.records}
    records = []
    for reference in hypothesis.evidence_refs:
        record = evidence_by_hash.get(reference)
        if record is None:
            raise ValueError("hypothesis references missing evidence")
        records.append(record)

    try:
        graph.traverse(hypothesis.state_hash)
    except KeyError as exc:
        raise ValueError("hypothesis state is absent from lineage graph") from exc

    count = len(records)
    distinct_sources = len({record.source_hash for record in records})
    density = count / (count + 1)
    independence = distinct_sources / count
    integrity = 1.0
    score = (density + independence + integrity) / 3
    if not 0.0 <= score <= 1.0:
        raise AssertionError("P22.9 score escaped the closed interval")
    return score
