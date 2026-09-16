"""EXP-11 / R0.1 adversarial test for the terminal EvidenceRecord state."""

import pytest

from jamp.research.causal_ledger import (
    CausalLedger,
    CausalOrderViolationError,
    EventTypeV0,
)

_HASH = "1" * 64
_RESULT_REF = "2" * 64
_EVIDENCE_REF = "3" * 64


def _completed_ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    prediction = ledger.append_prediction_commit(_HASH)
    execution_start = ledger.append_execution_start(prediction.event_hash, "exec-a")
    execution_result = ledger.append_execution_result(execution_start.event_hash, _RESULT_REF)
    ledger.append_evidence_record(execution_result.event_hash, _EVIDENCE_REF)
    return ledger


def test_terminal_evidence_state_rejects_any_following_event_atomically() -> None:
    ledger = _completed_ledger()
    payload = {"prediction_hash": _HASH}
    event = ledger.build_event(
        EventTypeV0.PREDICTION_COMMIT,
        ledger.event_count,
        ledger.head,
        payload,
    )
    before = ledger.snapshot()

    with pytest.raises(CausalOrderViolationError) as exc_info:
        ledger.append(event, payload=payload)

    assert exc_info.value.code == "CAUSAL_ORDER_VIOLATION"
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None
