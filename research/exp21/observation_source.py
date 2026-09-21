from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationSource:
    source_id: str
    model_id: str
    observation_ids: tuple[str, ...]
    model_version: str | None = None
    inference_params: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        if not self.model_id:
            raise ValueError("model_id must be non-empty")
        if not self.observation_ids:
            raise ValueError("observation_ids must be non-empty")
