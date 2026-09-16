"""EXP-11 research-only tests for EvidenceRecordV0 event binding."""

from __future__ import annotations

from dataclasses import dataclass, fields

import pytest

from jamp.research.canonical import replay_hash
from tests.research.test_evidence_record_v0 import EXPECTED_HASH, V0_001


@dataclass(frozen=True)
class ResearchEvent:
    """Minimal research-only provenance event boundary."""

    evidence_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_ref, str):
            raise TypeError("ResearchEvent.evidence_ref must be a hash reference string")


def _event_ref(event: ResearchEvent) -> str:
    return replay_hash({"evidence_ref": event.evidence_ref})


def _verify_chain(chain: list[ResearchEvent]) -> bool:
    if not chain:
        return False
    for index in range(1, len(chain)):
        if chain[index].evidence_ref != _event_ref(chain[index - 1]):
            return False
    return True


def test_t1_evidence_binding_is_deterministic() -> None:
    ref_a = replay_hash(V0_001)
    ref_b = replay_hash(V0_001)
    ref_c = replay_hash(dict(V0_001))

    assert ref_a == EXPECTED_HASH
    assert ref_b == EXPECTED_HASH
    assert ref_c == EXPECTED_HASH


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("payload", {"value": 43, "unit": "count"}),
        ("source_ref", "artifact:example-002"),
        ("observed_at", "2026-09-16T16:00:01Z"),
    ],
)
def test_t2_semantic_change_changes_evidence_ref(field: str, value: object) -> None:
    modified = dict(V0_001)
    modified[field] = value

    assert replay_hash(modified) != EXPECTED_HASH


def test_t3_a_event_accepts_hash_reference_not_raw_evidence() -> None:
    event = ResearchEvent(evidence_ref=EXPECTED_HASH)

    assert event.evidence_ref == EXPECTED_HASH

    with pytest.raises(TypeError, match="must be a hash reference string"):
        ResearchEvent(evidence_ref=V0_001)  # type: ignore[arg-type]


def test_t3_b_event_contains_only_evidence_ref() -> None:
    assert [field.name for field in fields(ResearchEvent)] == ["evidence_ref"]
    assert set(ResearchEvent.__annotations__) == {"evidence_ref"}


def test_t3_c_event_is_independent_of_evidence_structure() -> None:
    event = ResearchEvent(evidence_ref=replay_hash(V0_001))
    modified = dict(V0_001)
    modified["payload"] = {"value": 999, "unit": "count"}

    assert event.evidence_ref == EXPECTED_HASH
    assert replay_hash(modified) != event.evidence_ref
    assert event == ResearchEvent(evidence_ref=EXPECTED_HASH)


def test_t4_a_evidence_substitution_breaks_chain() -> None:
    event_a = ResearchEvent(evidence_ref=EXPECTED_HASH)
    event_b = ResearchEvent(evidence_ref=_event_ref(event_a))
    valid_chain = [event_a, event_b]

    substituted = ResearchEvent(evidence_ref=replay_hash({"evidence_ref": "substituted"}))
    invalid_chain = [event_a, substituted]

    assert _verify_chain(valid_chain)
    assert not _verify_chain(invalid_chain)


def test_t4_b_predecessor_substitution_breaks_chain() -> None:
    event_a = ResearchEvent(evidence_ref=EXPECTED_HASH)
    event_b = ResearchEvent(evidence_ref=_event_ref(event_a))
    alternate = ResearchEvent(evidence_ref=replay_hash({"evidence_ref": "alternate"}))
    broken = ResearchEvent(evidence_ref=_event_ref(alternate))

    assert _verify_chain([event_a, event_b])
    assert not _verify_chain([event_a, broken])


def test_t4_c_reordering_breaks_chain() -> None:
    event_a = ResearchEvent(evidence_ref=EXPECTED_HASH)
    event_b = ResearchEvent(evidence_ref=_event_ref(event_a))
    event_c = ResearchEvent(evidence_ref=_event_ref(event_b))

    assert _verify_chain([event_a, event_b, event_c])
    assert not _verify_chain([event_a, event_c, event_b])


def test_t5_replay_restores_and_verifies_chain() -> None:
    event_a = ResearchEvent(evidence_ref=EXPECTED_HASH)
    event_b = ResearchEvent(evidence_ref=_event_ref(event_a))
    event_c = ResearchEvent(evidence_ref=_event_ref(event_b))

    original = [event_a, event_b, event_c]
    persisted = [{"evidence_ref": event.evidence_ref} for event in original]
    restored = [ResearchEvent(**state) for state in persisted]

    assert [event.evidence_ref for event in restored] == [
        event.evidence_ref for event in original
    ]
    assert _verify_chain(restored)


def test_t5_replay_detects_tampered_state() -> None:
    event_a = ResearchEvent(evidence_ref=EXPECTED_HASH)
    event_b = ResearchEvent(evidence_ref=_event_ref(event_a))
    persisted = [
        {"evidence_ref": event_a.evidence_ref},
        {"evidence_ref": "tampered"},
    ]
    restored = [ResearchEvent(**state) for state in persisted]

    assert not _verify_chain(restored)
