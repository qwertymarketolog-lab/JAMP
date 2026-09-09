"""Fixtures for SPEC-E2E-1-SYNTHETIC-DISCOVERY-1.0.0."""
from __future__ import annotations

from dataclasses import dataclass

from jamp.research import canonical
from jamp.research.evidence import EvidenceLedger, EvidenceRecord, build_evidence_ledger
from jamp.research.hypothesis_formation import Hypothesis
from jamp.research.lineage_graph import LineageGraph, LineageNode, build_lineage_graph

SOURCE_1 = "1" * 64
SOURCE_2 = "2" * 64
SOURCE_9 = "9" * 64


def _hash(label: str) -> str:
    return canonical.replay_hash({"benchmark": "E2E-1-SYNTHETIC-DISCOVERY", "label": label})


OBS_A = _hash("obs_A")
OBS_B = _hash("obs_B")
OBS_C = _hash("obs_C")


def _graph() -> LineageGraph:
    return build_lineage_graph(
        (
            LineageNode(OBS_A, ()),
            LineageNode(OBS_B, (OBS_A,)),
            LineageNode(OBS_C, (OBS_B,)),
        )
    )


def _record(source_hash: str, payload_label: str, state_hash: str, sequence: int) -> EvidenceRecord:
    return EvidenceRecord(
        source_hash=source_hash,
        payload_hash=_hash(payload_label),
        state_hash=state_hash,
        sequence=sequence,
    )


def _hypothesis(
    evidence: tuple[EvidenceRecord, ...],
    state_hash: str,
    proposition: str,
) -> Hypothesis:
    return Hypothesis(
        evidence_refs=tuple(record.evidence_hash for record in evidence),
        state_hash=state_hash,
        proposition=proposition,
        sequence=0,
    )


@dataclass(frozen=True)
class TickFixture:
    graph: LineageGraph
    ledger: EvidenceLedger
    hypothesis_h1: Hypothesis
    hypothesis_h2: Hypothesis | None
    hypothesis_h3: Hypothesis | None
    expected_score_h1: float
    expected_score_h2: float | None


def create_tick_1_fixture() -> TickFixture:
    record_a = _record(SOURCE_1, "payload_A", OBS_A, 0)
    ledger = build_evidence_ledger((record_a,))
    h1 = _hypothesis((record_a,), OBS_A, "H1: obs_A")
    return TickFixture(
        graph=_graph(),
        ledger=ledger,
        hypothesis_h1=h1,
        hypothesis_h2=None,
        hypothesis_h3=None,
        expected_score_h1=5.0 / 6.0,
        expected_score_h2=None,
    )


def create_tick_2_fixture() -> TickFixture:
    record_a = _record(SOURCE_1, "payload_A_at_B", OBS_B, 0)
    record_b = _record(SOURCE_2, "payload_B", OBS_B, 1)
    record_b_same_source = _record(SOURCE_1, "payload_B_same_source", OBS_B, 2)
    ledger = build_evidence_ledger((record_a, record_b, record_b_same_source))
    h1 = _hypothesis((record_a, record_b), OBS_B, "H1: obs_A -> obs_B")
    h2 = _hypothesis((record_a, record_b_same_source), OBS_B, "H2: competing sibling")
    return TickFixture(
        graph=_graph(),
        ledger=ledger,
        hypothesis_h1=h1,
        hypothesis_h2=h2,
        hypothesis_h3=None,
        expected_score_h1=8.0 / 9.0,
        expected_score_h2=13.0 / 18.0,
    )


def create_tick_3_fixture() -> TickFixture:
    corrupt = _record(SOURCE_9, "payload_C_corrupt", OBS_C, 0)
    ledger = build_evidence_ledger((corrupt,))
    # Corrupt the content-addressed record after construction; verification
    # must reject it before any positive support is returned.
    object.__setattr__(corrupt, "evidence_hash", "0" * 64)
    h3 = _hypothesis((corrupt,), OBS_C, "H3: corrupt evidence")
    return TickFixture(
        graph=_graph(),
        ledger=ledger,
        hypothesis_h1=h3,
        hypothesis_h2=None,
        hypothesis_h3=h3,
        expected_score_h1=0.0,
        expected_score_h2=None,
    )
