"""Fail-closed contract for the JAMP Furniture Validator v1.

The canonical cabinet specification must be transcribed from source drawings.
This module deliberately does not embed inferred or fabricated part data.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Sequence


class ValidationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    HOLD = "HOLD"
    REFUSE = "REFUSE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class PartSpec:
    part_id: str
    length_mm: float
    width_mm: float
    thickness_mm: float
    material: str
    quantity: int


@dataclass(frozen=True)
class MeasurementRecord:
    part_id: str
    length_mm: float | None
    width_mm: float | None
    thickness_mm: float | None
    material: str | None
    quantity: int | None
    hole_reference: str | None
    source_readable: bool = True


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    reasons: tuple[str, ...]
    expected_parts: int
    matched_parts: int


class FurnitureValidator:
    """Validate measured cabinet parts against an explicit canonical specification."""

    def __init__(
        self,
        expected_parts: Sequence[PartSpec],
        *,
        dimension_tolerance_mm: float = 1.0,
        expected_part_count: int = 23,
        authorized_materials: set[str] | frozenset[str] | None = None,
    ) -> None:
        self._parts = tuple(expected_parts)
        self._tolerance = dimension_tolerance_mm
        self._expected_count = expected_part_count
        self._authorized_materials = (
            frozenset(authorized_materials) if authorized_materials is not None else None
        )

    def validate(self, measurements: Sequence[MeasurementRecord]) -> ValidationResult:
        reasons: list[str] = []
        expected = {part.part_id: part for part in self._parts}

        if not self._parts or len(self._parts) != self._expected_count:
            return self._result(
                ValidationStatus.INCONCLUSIVE,
                ("CANONICAL_SPECIFICATION_MISSING_OR_WRONG_CARDINALITY",),
                0,
            )
        if len(expected) != len(self._parts) or any(not part_id for part_id in expected):
            return self._result(ValidationStatus.INCONCLUSIVE, ("INVALID_SPECIFICATION_IDS",), 0)
        if not isfinite(self._tolerance) or self._tolerance < 0:
            return self._result(ValidationStatus.INCONCLUSIVE, ("INVALID_TOLERANCE",), 0)

        seen: set[str] = set()
        matched = 0
        missing_required = False
        hard_violation = False
        unreadable = False

        for record in measurements:
            if not record.source_readable:
                unreadable = True
                reasons.append(f"UNREADABLE_MEASUREMENT:{record.part_id or '<missing>'}")
                continue
            if not record.part_id or record.part_id not in expected:
                unreadable = True
                reasons.append(f"UNKNOWN_PART_ID:{record.part_id or '<missing>'}")
                continue
            if record.part_id in seen:
                hard_violation = True
                reasons.append(f"DUPLICATE_PART_ID:{record.part_id}")
                continue
            seen.add(record.part_id)
            spec = expected[record.part_id]

            required_values = (
                record.length_mm,
                record.width_mm,
                record.thickness_mm,
                record.material,
                record.quantity,
                record.hole_reference,
            )
            if any(value is None or value == "" for value in required_values):
                missing_required = True
                reasons.append(f"MISSING_REQUIRED_FIELD:{record.part_id}")
                continue

            dimensions = (record.length_mm, record.width_mm, record.thickness_mm)
            if any(not isfinite(value) or value <= 0 for value in dimensions if value is not None):
                unreadable = True
                reasons.append(f"INVALID_DIMENSION:{record.part_id}")
                continue

            if record.material != spec.material:
                hard_violation = True
                reasons.append(f"MATERIAL_MISMATCH:{record.part_id}")
                continue
            if self._authorized_materials is not None and record.material not in self._authorized_materials:
                hard_violation = True
                reasons.append(f"UNAUTHORIZED_MATERIAL:{record.part_id}")
                continue
            if record.quantity != spec.quantity:
                hard_violation = True
                reasons.append(f"QUANTITY_MISMATCH:{record.part_id}")
                continue
            if any(
                abs(actual - target) > self._tolerance
                for actual, target in zip(dimensions, (
                    spec.length_mm, spec.width_mm, spec.thickness_mm
                ), strict=True)
            ):
                hard_violation = True
                reasons.append(f"DIMENSION_OUT_OF_TOLERANCE:{record.part_id}")
                continue
            matched += 1

        missing_ids = set(expected) - seen
        if missing_ids:
            missing_required = True
            reasons.extend(f"MISSING_PART:{part_id}" for part_id in sorted(missing_ids))

        if unreadable:
            status = ValidationStatus.INCONCLUSIVE
        elif hard_violation:
            status = ValidationStatus.REFUSE
        elif missing_required:
            status = ValidationStatus.HOLD
        elif matched == self._expected_count and len(seen) == self._expected_count:
            status = ValidationStatus.VERIFIED
        else:
            status = ValidationStatus.INCONCLUSIVE

        return self._result(status, tuple(reasons), matched)

    def _result(
        self,
        status: ValidationStatus,
        reasons: tuple[str, ...],
        matched: int,
    ) -> ValidationResult:
        return ValidationResult(status, reasons, self._expected_count, matched)


__all__ = [
    "FurnitureValidator",
    "MeasurementRecord",
    "PartSpec",
    "ValidationResult",
    "ValidationStatus",
]
