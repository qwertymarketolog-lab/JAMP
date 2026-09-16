"""Independent acceptance gates for the P19.3 ResearchArtifact container."""

from __future__ import annotations

import hashlib

import pytest

from jamp.research.artifact import ResearchArtifact, ResearchArtifactError
from jamp.research.canonical import replay_hash
from jamp.research.causal import CausalEvent


STATE_A = replay_hash({"state": "A"})
STATE_B = replay_hash({"state": "B"})


def make_events() -> tuple[CausalEvent, CausalEvent]:
    root = CausalEvent(event_type="observation", sequence=0, parent_ids=(), state_hash=STATE_A, payload={"value": 7})
    child = CausalEvent(event_type="action", sequence=1, parent_ids=(root.event_id,), state_hash=STATE_B, payload={"operation": "advance"})
    return root, child


def repro(state_hash: str = STATE_B) -> dict[str, object]:
    return {"state_hash": state_hash, "environment": "research-sandbox", "seed": 42}


def test_artifact_assembly_and_state_anchor() -> None:
    root, child = make_events()
    artifact = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(child, root), observations=({"event_id": root.event_id, "text": "signal observed"},), hypotheses=({"event_id": root.event_id, "claim": "advance is plausible"},), actions=({"event_id": child.event_id, "operation": "advance"},), outcomes=({"state_hash": STATE_B, "result": "accepted"},), reproducibility=repro())
    assert artifact.events == (root, child)
    assert artifact.replay_hash() == STATE_B
    assert artifact.artifact_id == hashlib.sha256(artifact.canonical_bytes()).hexdigest()


def test_canonical_serialization_is_order_invariant_for_mappings() -> None:
    root, child = make_events()
    left = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), observations=({"event_id": root.event_id, "a": 1, "b": 2},), reproducibility={"seed": 42, "environment": "sandbox", "state_hash": STATE_B})
    right = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(child, root), observations=({"b": 2, "a": 1, "event_id": root.event_id},), reproducibility={"environment": "sandbox", "state_hash": STATE_B, "seed": 42})
    assert left.canonical_bytes() == right.canonical_bytes()
    assert left.artifact_id == right.artifact_id


def test_artifact_is_immutable() -> None:
    root, child = make_events()
    artifact = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), reproducibility=repro())
    with pytest.raises((AttributeError, TypeError)):
        artifact.state_hash = STATE_A  # type: ignore[misc]
    with pytest.raises(TypeError):
        artifact.reproducibility["seed"] = 99  # type: ignore[index]


def test_unknown_event_lineage_is_rejected() -> None:
    root, child = make_events()
    with pytest.raises(ResearchArtifactError, match="unknown event_id"):
        ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), observations=({"event_id": "f" * 64, "text": "orphan"},), reproducibility=repro())


def test_state_provenance_must_match_artifact_anchor() -> None:
    root, child = make_events()
    with pytest.raises(ResearchArtifactError, match="must match"):
        ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), outcomes=({"state_hash": STATE_A, "result": "wrong anchor"},), reproducibility=repro())


def test_semantic_records_require_exactly_one_provenance_anchor() -> None:
    root, child = make_events()
    with pytest.raises(ResearchArtifactError, match="exactly one"):
        ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), observations=({"text": "unanchored"},), reproducibility=repro())
    with pytest.raises(ResearchArtifactError, match="exactly one"):
        ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), observations=({"event_id": root.event_id, "state_hash": STATE_B},), reproducibility=repro())


def test_state_anchor_must_exist_in_causal_history() -> None:
    root, _ = make_events()
    with pytest.raises(ResearchArtifactError, match="anchored"):
        ResearchArtifact(schema_version="P19.3", state_hash=replay_hash({"state": "C"}), events=(root,), reproducibility=repro())


def test_reproducibility_metadata_requires_lineage() -> None:
    root, child = make_events()
    with pytest.raises(ResearchArtifactError, match="provenance"):
        ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child))
    with pytest.raises(ResearchArtifactError, match="must match"):
        ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), reproducibility={"state_hash": STATE_A, "seed": 42})


def test_payloads_and_reproducibility_are_canonicalizable() -> None:
    root, child = make_events()
    artifact = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), observations=({"event_id": root.event_id, "nested": {"x": [1, 2]}},), reproducibility={"state_hash": STATE_B, "seed": 42, "tags": ["linux", "python"]})
    encoded = artifact.canonical_bytes()
    assert isinstance(encoded, bytes)
    assert encoded == artifact.canonical_bytes()


def test_research_artifact_source_isolated_from_production_loops() -> None:
    from pathlib import Path
    source = Path(__file__).resolve().parents[2] / "src" / "jamp" / "research" / "artifact.py"
    text = source.read_text(encoding="utf-8")
    forbidden = ("jamp.domain", "Registry", "CommitManager", "commit_manager", "registry")
    assert [token for token in forbidden if token in text] == []


def test_artifact_identity_changes_when_research_content_changes() -> None:
    root, child = make_events()
    first = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), hypotheses=({"event_id": root.event_id, "claim": "A"},), reproducibility=repro())
    second = ResearchArtifact(schema_version="P19.3", state_hash=STATE_B, events=(root, child), hypotheses=({"event_id": root.event_id, "claim": "B"},), reproducibility=repro())
    assert first.artifact_id != second.artifact_id
