"""Research-only EXP-17-CV-R0 Visual Observation contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from jamp.research.canonical import replay_hash


class EpistemicStatus(StrEnum):
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    SUPPORTED = "SUPPORTED"


@dataclass(frozen=True)
class ObservationRecordR0:
    image_hash: str
    model_id: str
    model_version: str
    inference_params: tuple[tuple[str, str], ...]
    observation: str
    confidence: float

    def __post_init__(self) -> None:
        required = {
            "image_hash": self.image_hash,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "observation": self.observation,
        }
        if any(not value for value in required.values()):
            raise ValueError("ObservationRecord fields must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def canonical(self) -> dict[str, Any]:
        return {
            "image_hash": self.image_hash,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "inference_params": self.inference_params,
            "observation": self.observation,
            "confidence": self.confidence,
        }

    @property
    def provenance_ref(self) -> str:
        return replay_hash(self.canonical())


def image_hash(image_bytes: bytes) -> str:
    return sha256(image_bytes).hexdigest()


def evaluate_observation(record: ObservationRecordR0) -> EpistemicStatus:
    """CV confidence is model output, never epistemic truth."""
    _ = record
    return EpistemicStatus.NOT_SUPPORTED


def test_exp17_observation_records_image_provenance() -> None:
    record = ObservationRecordR0(
        image_hash=image_hash(b"fixture-image"),
        model_id="cv-fixture",
        model_version="1.0.0",
        inference_params=(("threshold", "0.50"),),
        observation="object-x",
        confidence=0.94,
    )

    assert record.image_hash == image_hash(b"fixture-image")
    assert record.provenance_ref


def test_exp17_same_input_model_and_parameters_are_reproducible() -> None:
    kwargs = {
        "image_hash": image_hash(b"fixture-image"),
        "model_id": "cv-fixture",
        "model_version": "1.0.0",
        "inference_params": (("threshold", "0.50"),),
        "observation": "object-x",
        "confidence": 0.94,
    }

    first = ObservationRecordR0(**kwargs)
    second = ObservationRecordR0(**kwargs)

    assert first.canonical() == second.canonical()
    assert first.provenance_ref == second.provenance_ref


def test_exp17_model_version_change_creates_new_provenance() -> None:
    common = {
        "image_hash": image_hash(b"fixture-image"),
        "model_id": "cv-fixture",
        "inference_params": (("threshold", "0.50"),),
        "observation": "object-x",
        "confidence": 0.94,
    }

    old = ObservationRecordR0(model_version="1.0.0", **common)
    new = ObservationRecordR0(model_version="1.1.0", **common)

    assert old.provenance_ref != new.provenance_ref


def test_exp17_model_change_creates_new_provenance() -> None:
    common = {
        "image_hash": image_hash(b"fixture-image"),
        "inference_params": (("threshold", "0.50"),),
        "observation": "object-x",
        "confidence": 0.94,
        "model_version": "1.0.0",
    }

    first = ObservationRecordR0(model_id="cv-fixture-a", **common)
    second = ObservationRecordR0(model_id="cv-fixture-b", **common)

    assert first.provenance_ref != second.provenance_ref


def test_exp17_inference_parameter_change_creates_new_provenance() -> None:
    common = {
        "image_hash": image_hash(b"fixture-image"),
        "model_id": "cv-fixture",
        "model_version": "1.0.0",
        "observation": "object-x",
        "confidence": 0.94,
    }

    first = ObservationRecordR0(inference_params=(("threshold", "0.50"),), **common)
    second = ObservationRecordR0(inference_params=(("threshold", "0.75"),), **common)

    assert first.provenance_ref != second.provenance_ref


def test_exp17_high_confidence_does_not_auto_promote_to_supported() -> None:
    record = ObservationRecordR0(
        image_hash=image_hash(b"fixture-image"),
        model_id="cv-fixture",
        model_version="1.0.0",
        inference_params=(("threshold", "0.50"),),
        observation="object-x",
        confidence=0.99,
    )

    assert evaluate_observation(record) is EpistemicStatus.NOT_SUPPORTED


def test_exp17_confidence_is_preserved_as_model_metric() -> None:
    record = ObservationRecordR0(
        image_hash=image_hash(b"fixture-image"),
        model_id="cv-fixture",
        model_version="1.0.0",
        inference_params=(("threshold", "0.50"),),
        observation="object-x",
        confidence=0.99,
    )

    assert record.confidence == 0.99
    assert record.confidence != EpistemicStatus.SUPPORTED


def test_exp17_record_is_immutable() -> None:
    record = ObservationRecordR0(
        image_hash=image_hash(b"fixture-image"),
        model_id="cv-fixture",
        model_version="1.0.0",
        inference_params=(("threshold", "0.50"),),
        observation="object-x",
        confidence=0.94,
    )

    try:
        record.confidence = 0.99  # type: ignore[misc]
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("ObservationRecordR0 must remain immutable")
