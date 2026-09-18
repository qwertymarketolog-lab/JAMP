from __future__ import annotations

from .fixtures_text import FIXTURES
from .text_adapter import TextObservation, adapt, normalize_text, provenance_digest


def test_a1_a2_normalization_is_deterministic_and_idempotent() -> None:
    for fixture in FIXTURES:
        first = normalize_text(fixture.raw_text)
        second = normalize_text(fixture.raw_text)
        assert first == second
        assert normalize_text(first) == first


def test_a1_a2_unicode_equivalent_inputs_share_normalized_payload() -> None:
    assert normalize_text("Caf\\u00e9") == normalize_text("Cafe\\u0301")


def test_p1_p2_provenance_recomputes_exactly() -> None:
    for fixture in FIXTURES:
        record = adapt(fixture)
        assert record["provenance_hash"] == provenance_digest(
            fixture,
            record["normalized_text"],
            record["adapter_id"],
            record["adapter_version"],
        )


def test_p1_p2_source_or_payload_change_changes_identity() -> None:
    fixture = FIXTURES[0]
    original = adapt(fixture)
    changed_source = adapt(TextObservation("fixture:text:changed", fixture.raw_text, fixture.metadata))
    changed_payload = adapt(TextObservation(fixture.source_ref, fixture.raw_text + "x", fixture.metadata))
    assert original["provenance_hash"] != changed_source["provenance_hash"]
    assert original["provenance_hash"] != changed_payload["provenance_hash"]


def test_adapter_does_not_mutate_input_metadata() -> None:
    fixture = FIXTURES[0]
    before = dict(fixture.metadata)
    adapt(fixture)
    assert fixture.metadata == before
