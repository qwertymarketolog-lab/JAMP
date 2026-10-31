from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from jamp.research.canonical import canonical_bytes


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "docs/research/specifications/SPECIFICATION-MANIFEST-v0.json"
SCHEMA_PATH = REPO_ROOT / "docs/research/specifications/specification-schema-v0.json"
SPEC_ID_NAMESPACE = uuid.UUID("5c9426b4-f92f-5742-a2b4-8a244a411708")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compute_spec_id(specification: dict) -> str:
    payload = {
        key: value
        for key, value in specification.items()
        if key not in {"spec_id", "spec_hash", "frozen_at"}
    }
    # UUIDv5 accepts a string; decoding preserves the canonical UTF-8 byte sequence.
    return str(uuid.uuid5(SPEC_ID_NAMESPACE, canonical_bytes(payload).decode("utf-8")))


def _compute_spec_hash(specification: dict) -> str:
    payload = {key: value for key, value in specification.items() if key != "spec_hash"}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def test_schema_file_sha256_matches_manifest() -> None:
    manifest = _load_json(MANIFEST_PATH)
    actual = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()

    assert manifest["specification_schema"]["file_sha256"] == actual


def test_manifest_required_fields_match_schema() -> None:
    manifest = _load_json(MANIFEST_PATH)
    schema = _load_json(SCHEMA_PATH)

    assert set(manifest["specification_schema"]["required_fields"]) == set(schema["required"])


def test_spec_id_namespace_reproducible() -> None:
    expected = uuid.UUID("5c9426b4-f92f-5742-a2b4-8a244a411708")

    assert uuid.uuid5(
        uuid.NAMESPACE_DNS, "jamp.dev/specifications/spec-id"
    ) == expected


def test_spec_id_semantics_ratified_in_manifest() -> None:
    semantics = _load_json(MANIFEST_PATH)["spec_id_semantics"]

    assert semantics["status"] == "RATIFIED"
    assert semantics["freeze_blocker"] is False
    assert semantics["spec_id_namespace"] == str(SPEC_ID_NAMESPACE)
    assert semantics["namespace_root"] == str(uuid.NAMESPACE_DNS)
    assert semantics["namespace_name"] == "jamp.dev/specifications/spec-id"


def test_spec_id_excludes_frozen_at() -> None:
    draft = {
        "spec_id": "placeholder",
        "spec_version": "0.1.0",
        "hypothesis_ref": "a" * 64,
        "prediction_ref": "b" * 64,
        "criterion_set_ref": "c" * 64,
        "preconditions": [{"kind": "runtime", "value": {"python": ">=3.11"}}],
        "scope": {"in_scope": ["unit"], "out_of_scope": ["production"]},
        "evidence_classes": ["raw_webhook_payload"],
        "observation_schema": {"fields": [{"name": "status", "type": "string"}]},
        "frozen_at": None,
        "spec_hash": "0" * 64,
    }
    frozen = {**draft, "frozen_at": "2026-10-31T12:00:00Z"}

    assert _compute_spec_id(draft) == _compute_spec_id(frozen)


def test_spec_hash_includes_frozen_at() -> None:
    draft = {
        "spec_id": "spec-1",
        "spec_version": "0.1.0",
        "hypothesis_ref": "a" * 64,
        "prediction_ref": "b" * 64,
        "criterion_set_ref": "c" * 64,
        "preconditions": [{"kind": "runtime", "value": {"python": ">=3.11"}}],
        "scope": {"in_scope": ["unit"], "out_of_scope": ["production"]},
        "evidence_classes": ["raw_webhook_payload"],
        "observation_schema": {"fields": [{"name": "status", "type": "string"}]},
        "frozen_at": None,
        "spec_hash": "0" * 64,
    }
    frozen = {**draft, "frozen_at": "2026-10-31T12:00:00Z"}

    assert _compute_spec_hash(draft) != _compute_spec_hash(frozen)
