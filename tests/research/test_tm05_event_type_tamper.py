"""EXP-11 / TM-05 event-type tamper tests."""

import pytest

from jamp.research.causal_ledger import (
    CausalEventV0,
    CausalLedger,
    CausalOrderViolationError,
    EventTypeV0,
    ExecutionStartMissingError,
    GenesisViolationError,
    LedgerError,
)

_HASH = "1" * 64


def _ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    ledger.append_prediction_commit(_HASH)
    return ledger


def test_tm05_unsupported_event_type_is_rejected_atomically() -> None:
    ledger = _ledger()
    before = ledger.snapshot()

    with pytest.raises(LedgerError, match="invalid event_type"):
        CausalEventV0(
            event_type="UNSUPPORTED",
            event_version="0",
            sequence_index=2,
            parent_hash=ledger.head,
            payload_hash=_HASH,
            event_hash=_HASH,
        )

    assert ledger.snapshot() == before
    assert ledger.event_count == 2
    assert ledger.head == before.head


@pytest.mark.parametrize("event_type", ["", "NOT_AN_EVENT"])
def test_tm05_invalid_or_empty_event_type_is_rejected_atomically(
    event_type: str,
) -> None:
    ledger = _ledger()
    before = ledger.snapshot()

    with pytest.raises(LedgerError, match="invalid event_type"):
        CausalEventV0(
            event_type=event_type,
            event_version="0",
            sequence_index=2,
            parent_hash=ledger.head,
            payload_hash=_HASH,
            event_hash=_HASH,
        )

    assert ledger.snapshot() == before


def test_tm05_event_type_payload_mismatch_preserves_l0() -> None:
    ledger = _ledger()
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        2,
        ledger.head,
        payload,
    )
    before = ledger.snapshot()

    with pytest.raises(CausalOrderViolationError) as exc_info:
        ledger.append(event, payload=payload)

    assert exc_info.value.code == CausalOrderViolationError.code
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None


def test_tm05_supported_wrong_type_is_rejected_by_causal_contract() -> None:
    ledger = _ledger()
    payload = {"execution_start_hash": ledger.head, "result_ref": _HASH}
    event = ledger.build_event(
        EventTypeV0.EXECUTION_RESULT,
        2,
        ledger.head,
        payload,
    )
    before = ledger.snapshot()

    with pytest.raises(ExecutionStartMissingError) as exc_info:
        ledger.append(event, payload=payload)

    assert exc_info.value.code == ExecutionStartMissingError.code
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None


def test_tm05_genesis_type_tamper_is_rejected_without_mutation() -> None:
    ledger = _ledger()
    payload = {}
    event = ledger.build_event(
        EventTypeV0.GENESIS,
        2,
        ledger.head,
        payload,
    )
    before = ledger.snapshot()

    with pytest.raises(GenesisViolationError) as exc_info:
        ledger.append(event, payload=payload)

    assert exc_info.value.code == GenesisViolationError.code
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None
