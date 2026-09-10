"""Example extension boundary for JAMP."""

from __future__ import annotations

from typing import Any, Protocol


class EnginePlugin(Protocol):
    """Minimal adapter surface; implementations must remain deterministic."""

    name: str

    def propose(self, observation: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        """Return candidate proposals without mutating the observation."""
        ...


class ExampleEngine:
    name = "example-engine"

    def propose(self, observation: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        return ({"kind": "candidate", "observation": dict(observation)},)
