"""Research-only deterministic text adapter harness for EXP-20 Step 1."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TextObservation:
    source_ref: str
    raw_text: str
    metadata: dict[str, Any]


def normalize_text(raw_text: str) -> str:
    """A1/A2 fixture normalization: Unicode canonicalization + stable whitespace."""
    text = unicodedata.normalize("NFC", raw_text)
    return " ".join(text.split())


def canonical_bytes(value: Any) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return payload.encode("utf-8")


def provenance_digest(
    observation: TextObservation,
    normalized_text: str,
    adapter_id: str,
    adapter_version: str,
) -> str:
    """P1/P2 binding over source identity, adapter identity, metadata and normalized payload."""
    envelope = {
        "source_ref": observation.source_ref,
        "source_type": "text",
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "normalized_text": normalized_text,
        "metadata": observation.metadata,
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def adapt(observation: TextObservation) -> dict[str, Any]:
    normalized = normalize_text(observation.raw_text)
    adapter_id = "exp20.text"
    adapter_version = "0.1"
    return {
        "source_ref": observation.source_ref,
        "source_type": "text",
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "normalized_text": normalized,
        "metadata": dict(observation.metadata),
        "provenance_hash": provenance_digest(observation, normalized, adapter_id, adapter_version),
    }
