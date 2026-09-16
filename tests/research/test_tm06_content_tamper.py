"""EXP-11 / TM-06 content tamper tests."""

import pytest

from jamp.research.causal_ledger import (
    CausalLedger,
    EventHashMismatchError,
    PayloadHashMismatchError,
)

_HASH = "1" * 64


def _ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    ledger.append_prediction_commit(_HASH)
    return ledger


def test_tm06_payload_mutation_is_rejected_atomically() -> None:
    ledger = _ledger()
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = ledger.build_event(
        event_type="EXECUTION_START",
        sequence_index=2,
        parent_hash=ledger.head,
        payload=payload,
    )
    before = ledger.snapshot()
    tampered_payload = {**payload, "execution_id": "exec-tampered"}

    with pytest.raises(PayloadHashMismatchError) as exc_info:
        ledger.append(event, payload=tampered_payload)

    assert exc_info.value.code == PayloadHashMismatchError.code
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None


def test_tm06_content_tamper_cannot_be_hidden_by_original_payload_hash() -> None:
    ledger = _ledger()
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = ledger.build_event(
        event_type="EXECUTION_START",
        sequence_index=2,
        parent_hash=ledger.head,
        payload=payload,
    )
    before = ledger.snapshot()
    tampered_event = event.__class__(
        event_type=event.event_type,
        event_version=event.event_version,
        sequence_index=event.sequence_index,
        parent_hash=event.parent_hash,
        payload_hash=event.payload_hash,
        event_hash="2" * 64,
    )

    with pytest.raises(EventHashMismatchError) as exc_info:
        ledger.append(tampered_event, payload=payload)

    assert exc_info.value.code == EventHashMismatchError.code
    assert ledger.snapshot() == before
    assert ledger.get(tampered_event.event_hash) is None


def test_tm06_payload_mutation_preserves_previous_head_and_events() -> None:
    ledger = _ledger()
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = ledger.build_event(
        event_type="EXECUTION_START",
        sequence_index=2,
        parent_hash=ledger.head,
        payload=payload,
    )
    before = ledger.snapshot()

    with pytest.raises(PayloadHashMismatchError):
        ledger.append(
            event,
            payload={"execution_id": "exec-a", "prediction_commit_hash": _HASH},
        )

    assert ledger.snapshot() == before
    assert ledger.get(ledger.head) is not None
    assert ledger.event_count == 2
