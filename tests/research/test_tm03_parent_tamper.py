"""EXP-11 R0.2 TM-03 parent-hash tamper matrix."""

import pytest

from jamp.research.causal_ledger import (
    ZERO_HASH,
    CausalLedger,
    EventTypeV0,
    LedgerError,
    ParentMissingError,
)

_HASH = "1" * 64


def _ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    return ledger


def _event(ledger: CausalLedger, parent_hash: str):
    payload = {"prediction_hash": _HASH}
    return ledger.build_event(
        EventTypeV0.PREDICTION_COMMIT,
        ledger.event_count,
        parent_hash,
        payload,
    ), payload


def _assert_rejected_without_mutation(
    ledger: CausalLedger,
    event,
    payload,
    expected: type[LedgerError],
) -> None:
    before = ledger.snapshot()
    with pytest.raises(expected) as exc_info:
        ledger.append(event, payload=payload)
    assert exc_info.value.code == expected.code
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None


def test_tm03_nonexistent_parent_hash_is_rejected_atomically() -> None:
    ledger = _ledger()
    event, payload = _event(ledger, "9" * 64)
    _assert_rejected_without_mutation(ledger, event, payload, ParentMissingError)


def test_tm03_foreign_branch_parent_hash_is_rejected_atomically() -> None:
    ledger = _ledger()
    foreign = _ledger()
    foreign_event = foreign.append_prediction_commit("4" * 64)
    event, payload = _event(ledger, foreign_event.event_hash)
    _assert_rejected_without_mutation(ledger, event, payload, ParentMissingError)


def test_tm03_zero_parent_hash_mid_chain_is_rejected_atomically() -> None:
    ledger = _ledger()
    ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = ledger.build_event(
        EventTypeV0.EXECUTION_START,
        ledger.event_count,
        ZERO_HASH,
        payload,
    )
    _assert_rejected_without_mutation(ledger, event, payload, ParentMissingError)
