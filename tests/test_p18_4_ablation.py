from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from jamp.p18.controlled_transfer import ControlledTransfer
from jamp.p18.transfer_contracts import (
    FAMILY_A,
    FAMILY_B,
    FAMILY_C,
    Projection,
    TransferAuthorization,
)


def _source() -> dict[str, object]:
    return {
        "family_id": FAMILY_A,
        "task_id": "task-a",
        "pattern_id": "pattern-a",
        "payload": {"signal": "stable", "weight": 7},
    }


def _authorization(source: dict[str, object], source_family: str = FAMILY_A) -> TransferAuthorization:
    return TransferAuthorization(
        authorization_id="AUTH-P18.4-001",
        source_family=source_family,
        target_family=FAMILY_B,
        source_digest=hashlib.sha256(repr(source).encode()).hexdigest(),
        authorization_digest=hashlib.sha256(b"AUTH-P18.4-001").hexdigest(),
        policy_reason="controlled ablation baseline",
    )


def _projection(
    source: dict[str, object],
    authorization: TransferAuthorization,
    shared_payload: bool = False,
) -> Projection:
    return Projection(
        projection_id="PROJ-P18.4-001",
        source_family=source["family_id"],
        target_family=authorization.target_family,
        source_pattern_id=source["pattern_id"],
        projected_payload=source["payload"] if shared_payload else {"signal": "stable", "weight": 8},
        authorization_id=authorization.authorization_id,
        projection_digest=hashlib.sha256(b"PROJ-P18.4-001").hexdigest(),
    )


def _gateway() -> ControlledTransfer:
    return ControlledTransfer(
        authorization_required=True,
        isolation_required=True,
    )


def test_p18_4_baseline_authorization_enabled_blocks_foreign_authority():
    source = _source()
    authorization = _authorization(source, source_family=FAMILY_C)
    projection = _projection(source, authorization)

    with pytest.raises(ValueError, match="authorization source family does not own source pattern"):
        _gateway().transfer(
            source_pattern=source,
            authorization=authorization,
            projection=projection,
        )


def test_p18_4_baseline_isolation_enabled_rejects_shared_payload():
    source = _source()
    authorization = _authorization(source)
    projection = _projection(source, authorization, shared_payload=True)

    with pytest.raises(ValueError):
        _gateway().transfer(
            source_pattern=source,
            authorization=authorization,
            projection=projection,
        )


def test_p18_4_ablation_without_authorization_guardrail_allows_transfer():
    source = _source()
    authorization = _authorization(source)
    projection = _projection(source, authorization)

    result = ControlledTransfer(
        authorization_required=False,
        isolation_required=True,
    ).transfer(
        source_pattern=source,
        authorization=authorization,
        projection=projection,
    )

    assert result


def test_p18_4_ablation_without_isolation_guardrail_allows_shared_payload():
    source = _source()
    authorization = _authorization(source)
    projection = _projection(source, authorization, shared_payload=True)

    result = ControlledTransfer(
        authorization_required=True,
        isolation_required=False,
    ).transfer(
        source_pattern=source,
        authorization=authorization,
        projection=projection,
    )

    assert result


def test_p18_4_full_guardrails_preserve_source_and_target_boundaries():
    source = _source()
    authorization = _authorization(source)
    projection = _projection(source, authorization)

    result = _gateway().transfer(
        source_pattern=source,
        authorization=authorization,
        projection=projection,
    )

    assert result.source_family == FAMILY_A
    assert result.target_family == FAMILY_B


# Keep imported symbol usage explicit for static analyzers in the historical harness.
assert replace is not None
