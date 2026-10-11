"""Text Research/Audit Contract R0 executable specification.

This file is intentionally self-contained: no production TextAudit API exists yet.
"""

import hashlib
from dataclasses import dataclass
from enum import StrEnum

import pytest


class EpistemicStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"
    TAMPER_DETECTED = "TAMPER_DETECTED"


class ContractViolationError(ValueError):
    """Raised when a proposed epistemic state violates the R0.1 contract."""


@dataclass(frozen=True)
class AuditRecord:
    input_text: str
    normalized: str
    transformation: str
    observation: str
    conclusion: str
    evidence: tuple[str, ...]
    status: EpistemicStatus
    commitment: str


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _validate_status(record: AuditRecord) -> None:
    if record.status is EpistemicStatus.TAMPER_DETECTED:
        raise ContractViolationError("TAMPER_DETECTED is an audit result, not a committed state")

    if record.status is EpistemicStatus.SUPPORTED:
        if not record.evidence:
            raise ContractViolationError("SUPPORTED requires non-empty evidence")
        if not record.transformation:
            raise ContractViolationError("SUPPORTED requires a recorded transformation")

    if record.status is EpistemicStatus.REJECTED:
        if not record.evidence:
            raise ContractViolationError("REJECTED requires evidence")
        if not any(item.startswith("contradiction:") for item in record.evidence):
            raise ContractViolationError(
                "REJECTED requires explicitly recorded contradictory evidence"
            )


def _commit(record: AuditRecord) -> str:
    payload = "\x1f".join(
        (
            record.input_text,
            record.normalized,
            record.transformation,
            record.observation,
            record.conclusion,
            *record.evidence,
            record.status.value,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _make_record(
    *,
    input_text: str,
    transformation: str,
    observation: str,
    conclusion: str,
    evidence: tuple[str, ...],
    status: EpistemicStatus,
) -> AuditRecord:
    record = AuditRecord(
        input_text=input_text,
        normalized=_normalize(input_text),
        transformation=transformation,
        observation=observation,
        conclusion=conclusion,
        evidence=evidence,
        status=status,
        commitment="",
    )
    _validate_status(record)
    return AuditRecord(**{**record.__dict__, "commitment": _commit(record)})


def _audit(record: AuditRecord) -> EpistemicStatus:
    if _commit(record) != record.commitment:
        return EpistemicStatus.TAMPER_DETECTED
    _validate_status(record)
    return record.status


def test_ta1_valid_pipeline_has_complete_provenance() -> None:
    record = _make_record(
        input_text="Observation: sample A",
        transformation="extract: sample A",
        observation="sample A is present",
        conclusion="sample A is supported",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )

    assert record.normalized == "Observation: sample A"
    assert _audit(record) is EpistemicStatus.SUPPORTED


def test_ta2_normalization_is_deterministic() -> None:
    text = "  alpha\n beta   gamma  "

    assert _normalize(text) == _normalize(text)
    assert _normalize(text) == "alpha beta gamma"


def test_ta3_input_mutation_is_detected() -> None:
    record = _make_record(
        input_text="original",
        transformation="identity",
        observation="original",
        conclusion="original is observed",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )
    tampered = AuditRecord(**{**record.__dict__, "input_text": "altered"})

    assert _audit(tampered) is EpistemicStatus.TAMPER_DETECTED


def test_ta4_transformation_mutation_is_detected() -> None:
    record = _make_record(
        input_text="alpha",
        transformation="identity",
        observation="alpha",
        conclusion="alpha observed",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )
    tampered = AuditRecord(**{**record.__dict__, "transformation": "substitute: beta"})

    assert _audit(tampered) is EpistemicStatus.TAMPER_DETECTED


def test_ta5_unsupported_evidence_cannot_be_marked_supported() -> None:
    with pytest.raises(ContractViolationError):
        _make_record(
            input_text="claim",
            transformation="extract claim",
            observation="no supporting evidence",
            conclusion="claim",
            evidence=(),
            status=EpistemicStatus.SUPPORTED,
        )


def test_ta6_insufficient_evidence_is_inconclusive() -> None:
    record = _make_record(
        input_text="claim",
        transformation="extract claim",
        observation="evidence is insufficient",
        conclusion="claim cannot yet be established",
        evidence=(),
        status=EpistemicStatus.INCONCLUSIVE,
    )

    assert _audit(record) is EpistemicStatus.INCONCLUSIVE


def test_ta7_contradictory_evidence_is_rejected() -> None:
    record = _make_record(
        input_text="claim",
        transformation="compare sources",
        observation="source-1 contradicts claim",
        conclusion="claim is rejected",
        evidence=("source-1", "contradiction:source-2"),
        status=EpistemicStatus.REJECTED,
    )

    assert _audit(record) is EpistemicStatus.REJECTED


def test_ta8_post_commit_mutation_is_tamper_detected() -> None:
    record = _make_record(
        input_text="alpha",
        transformation="identity",
        observation="alpha",
        conclusion="alpha",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )
    tampered = AuditRecord(**{**record.__dict__, "conclusion": "beta"})

    assert _audit(tampered) is EpistemicStatus.TAMPER_DETECTED


def test_ta9_repeated_audit_is_deterministic() -> None:
    record = _make_record(
        input_text="alpha",
        transformation="identity",
        observation="alpha",
        conclusion="alpha",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )

    assert [_audit(record) for _ in range(3)] == [EpistemicStatus.SUPPORTED] * 3


def test_ta10_no_hidden_repair_substitution_or_fallback() -> None:
    record = _make_record(
        input_text="alpha",
        transformation="identity",
        observation="alpha",
        conclusion="alpha",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )
    tampered = AuditRecord(**{**record.__dict__, "input_text": "beta"})

    with pytest.raises(AssertionError):
        assert _audit(tampered) is EpistemicStatus.SUPPORTED

    assert _audit(tampered) is EpistemicStatus.TAMPER_DETECTED


def test_ta11_inconclusive_cannot_escalate_to_supported_without_new_evidence() -> None:
    with pytest.raises(ContractViolationError):
        _make_record(
            input_text="claim",
            transformation="extract claim",
            observation="evidence is insufficient",
            conclusion="claim",
            evidence=(),
            status=EpistemicStatus.SUPPORTED,
        )


def test_ta12_rejected_cannot_escalate_to_supported_without_supporting_evidence() -> None:
    record = _make_record(
        input_text="claim",
        transformation="compare sources",
        observation="source-1 contradicts claim",
        conclusion="claim is rejected",
        evidence=("source-1", "contradiction:source-2"),
        status=EpistemicStatus.REJECTED,
    )
    tampered = AuditRecord(
        **{**record.__dict__, "status": EpistemicStatus.SUPPORTED}
    )

    assert _audit(tampered) is EpistemicStatus.TAMPER_DETECTED


def test_ta13_evidence_mutation_is_tamper_detected() -> None:
    record = _make_record(
        input_text="claim",
        transformation="extract claim",
        observation="claim is supported",
        conclusion="claim is supported",
        evidence=("source-1",),
        status=EpistemicStatus.SUPPORTED,
    )
    tampered = AuditRecord(
        **{**record.__dict__, "evidence": ("source-forged",)}
    )

    assert _audit(tampered) is EpistemicStatus.TAMPER_DETECTED


def test_ta14_tamper_detected_is_derived_not_committed() -> None:
    with pytest.raises(ContractViolationError):
        _make_record(
            input_text="alpha",
            transformation="identity",
            observation="alpha",
            conclusion="alpha",
            evidence=("source-1",),
            status=EpistemicStatus.TAMPER_DETECTED,
        )


def test_ta15_rejected_requires_explicit_contradiction_evidence() -> None:
    with pytest.raises(ContractViolationError):
        _make_record(
            input_text="claim",
            transformation="compare sources",
            observation="sources are insufficient",
            conclusion="claim is rejected",
            evidence=("source-1", "source-2"),
            status=EpistemicStatus.REJECTED,
        )
