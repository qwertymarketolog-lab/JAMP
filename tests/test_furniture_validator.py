"""Contract tests use synthetic records, not the Davydova cabinet source dataset."""
from src.jamp.furniture.validator import (
    FurnitureValidator, MeasurementRecord, PartSpec, ValidationStatus,
)


def specs():
    return tuple(PartSpec(f"P{i:02}", 600, 400, 16, "ЛДСП Кашемир Серый", 1) for i in range(1, 24))


def records(parts):
    return tuple(
        MeasurementRecord(p.part_id, p.length_mm, p.width_mm, p.thickness_mm,
                          p.material, p.quantity, f"REF-{p.part_id}")
        for p in parts
    )


def test_all_23_matching_synthetic_records_are_verified():
    parts = specs()
    result = FurnitureValidator(parts).validate(records(parts))
    assert result.status is ValidationStatus.VERIFIED
    assert result.matched_parts == 23


def test_missing_required_field_is_hold():
    parts = specs()
    values = list(records(parts))
    p = values[0]
    values[0] = MeasurementRecord(p.part_id, p.length_mm, p.width_mm, None,
                                  p.material, p.quantity, p.hole_reference)
    result = FurnitureValidator(parts).validate(values)
    assert result.status is ValidationStatus.HOLD


def test_material_mismatch_is_refused():
    parts = specs()
    values = list(records(parts))
    p = values[0]
    values[0] = MeasurementRecord(p.part_id, p.length_mm, p.width_mm, p.thickness_mm,
                                  "UNAUTHORIZED", p.quantity, p.hole_reference)
    result = FurnitureValidator(parts).validate(values)
    assert result.status is ValidationStatus.REFUSE


def test_out_of_tolerance_dimension_is_refused():
    parts = specs()
    values = list(records(parts))
    p = values[0]
    values[0] = MeasurementRecord(p.part_id, p.length_mm + 10, p.width_mm,
                                  p.thickness_mm, p.material, p.quantity, p.hole_reference)
    result = FurnitureValidator(parts).validate(values)
    assert result.status is ValidationStatus.REFUSE


def test_unknown_part_id_is_inconclusive():
    parts = specs()
    values = list(records(parts))
    values[0] = MeasurementRecord("NOT-IN-SCHEMA", 600, 400, 16,
                                  "ЛДСП Кашемир Серый", 1, "REF")
    result = FurnitureValidator(parts).validate(values)
    assert result.status is ValidationStatus.INCONCLUSIVE


def test_empty_canonical_specification_is_inconclusive():
    result = FurnitureValidator(()).validate(())
    assert result.status is ValidationStatus.INCONCLUSIVE


def test_duplicate_part_id_is_refused():
    parts = specs()
    values = list(records(parts))
    values[1] = values[0]
    result = FurnitureValidator(parts).validate(values)
    assert result.status is ValidationStatus.REFUSE


def test_unreadable_measurement_is_inconclusive():
    parts = specs()
    values = list(records(parts))
    p = values[0]
    values[0] = MeasurementRecord(p.part_id, p.length_mm, p.width_mm, p.thickness_mm,
                                  p.material, p.quantity, p.hole_reference,
                                  source_readable=False)
    result = FurnitureValidator(parts).validate(values)
    assert result.status is ValidationStatus.INCONCLUSIVE


def test_incomplete_specification_is_hold():
    parts = specs()
    result = FurnitureValidator(parts).validate(records(parts[:-1]))
    assert result.status is ValidationStatus.HOLD
    assert "MISSING_PART:P23" in result.reasons
