"""EXP-11 / TM-07 event-version tamper tests."""

import pytest

from jamp.research.causal_ledger import CausalEventV0, CausalLedger, LedgerError

_HASH = "1" * 64


def _ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    ledger.append_prediction_commit(_HASH)
    return ledger


def test_tm07_invalid_event_version_is_rejected() -> None:
    ledger = _ledger()
    event = ledger.build_event(
        event_type="EXECUTION_START",
        sequence_index=2,
        parent_hash=ledger.head,
        payload={
            "execution_id": "exec-a",
            "prediction_commit_hash": ledger.head,
        },
    )
    before = ledger.snapshot()

    with pytest.raises(LedgerError) as exc_info:
        CausalEventV0(
            event_type=event.event_type,
            event_version="1",
            sequence_index=event.sequence_index,
            parent_hash=event.parent_hash,
            payload_hash=event.payload_hash,
            event_hash=event.event_hash,
        )

    assert str(exc_info.value) == "event_version must be '0'"
    assert ledger.snapshot() == before


def test_tm07_event_version_tamper_preserves_l0_state() -> None:
    ledger = _ledger()
    event = ledger.build_event(
        event_type="EXECUTION_START",
        sequence_index=2,
        parent_hash=ledger.head,
        payload={
            "execution_id": "exec-a",
            "prediction_commit_hash": ledger.head,
        },
    )
    before = ledger.snapshot()

    with pytest.raises(LedgerError):
        CausalEventV0(
            event_type=event.event_type,
            event_version="1",
            sequence_index=event.sequence_index,
            parent_hash=event.parent_hash,
            payload_hash=event.payload_hash,
            event_hash=event.event_hash,
        )

    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None
    assert ledger.event_count == 2


def test_tm07_only_version_zero_is_constructible_for_existing_event() -> None:
    ledger = _ledger()
    event = ledger.build_event(
        event_type="EXECUTION_START",
        sequence_index=2,
        parent_hash=ledger.head,
        payload={
            "execution_id": "exec-a",
            "prediction_commit_hash": ledger.head,
        },
    )

    valid = CausalEventV0(
        event_type=event.event_type,
        event_version="0",
        sequence_index=event.sequence_index,
        parent_hash=event.parent_hash,
        payload_hash=event.payload_hash,
        event_hash=event.event_hash,
    )

    assert valid.event_version == "0"
    assert valid.verify_event_hash()
