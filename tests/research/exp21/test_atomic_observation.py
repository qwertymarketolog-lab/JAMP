from __future__ import annotations

from ..exp20.fixtures_text import FIXTURES as TEXT_FIXTURES
from ..exp20.fixtures_transcript import FIXTURES as TRANSCRIPT_FIXTURES
from ..exp20.text_adapter import adapt as adapt_text
from ..exp20.transcript_adapter import adapt as adapt_transcript
from .atomic_observation import (
    SCHEMA_VERSION,
    from_text_record,
    from_transcript_record,
    observation_digest,
)

def test_text_record_maps_to_immutable_observation() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    observation = from_text_record(record)
    assert observation.schema_version == SCHEMA_VERSION
    assert observation.observation_id == observation.immutable_hash
    assert observation.immutable_hash == observation_digest(
        observation.source_ref, observation.payload
    )

def test_transcript_segments_map_one_to_one() -> None:
    record = adapt_transcript(TRANSCRIPT_FIXTURES[0])
    observations = from_transcript_record(record)
    assert len(observations) == len(record["segments"])
    assert [item.payload["segment_index"] for item in observations] == list(range(len(observations)))

def test_source_change_changes_observation_identity() -> None:
    record = adapt_text(TEXT_FIXTURES[0])
    original = from_text_record(record)
    changed = dict(record)
    changed["source_ref"] = "fixture:text:changed"
    replacement = from_text_record(changed)
    assert original.immutable_hash != replacement.immutable_hash
