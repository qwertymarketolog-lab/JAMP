from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationSource:
    source_id: str
    model_id: str
    observation_ids: tuple[str, ...]
    model_version: str | None = None
    inference_params: dict[str, object] | None = None
