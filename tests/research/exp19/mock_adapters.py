"""Deterministic research-only source adapters for EXP-19."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MockSignal:
    source_ref: str
    source_type: str
    payload: dict[str, Any]
    metadata: dict[str, Any]


class MockAdapter:
    def __init__(self, adapter_id: str, adapter_version: str, source_type: str) -> None:
        self.adapter_id = adapter_id
        self.adapter_version = adapter_version
        self.source_type = source_type

    def normalize(self, signal: MockSignal) -> dict[str, Any]:
        return {
            "source_ref": signal.source_ref,
            "source_type": signal.source_type,
            "payload": deepcopy(signal.payload),
            "metadata": deepcopy(signal.metadata),
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
        }


def make_signal(source_ref: str, source_type: str, content: str) -> MockSignal:
    return MockSignal(
        source_ref=source_ref,
        source_type=source_type,
        payload={"content": content},
        metadata={"fixture": "exp19"},
    )


def adapters() -> dict[str, MockAdapter]:
    return {
        kind: MockAdapter("exp19.mock", "0.1", kind)
        for kind in ("text", "transcript", "video_metadata", "ai_signal")
    }
