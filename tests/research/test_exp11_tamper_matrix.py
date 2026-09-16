"""EXP-11 / R0.2 adversarial tamper-matrix tests."""

from dataclasses import replace

import pytest

from jamp.research.causal_ledger import (
    CausalLedger,
    EventHashMismatchError,
)

_HASH = "1" * 64


def _prediction_commit_ledger() -> tuple[CausalLedger, object, dict[str, str]]:
    ledger = CausalLedger()
    ledger.append_genesis()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"prediction_hash": _HASH}
    return ledger, prediction, payload


def test_tm01_event_hash_tamper_is_rejected_atomically() -> None:
    ledger, event, payload = _prediction_commit_ledger()
    tampered = replace(event, event_hash="0" * 64)
    before = ledger.snapshot()

    with pytest.raises(EventHashMismatchError) as exc_info:
        ledger.append(tampered, payload=payload)

    assert exc_info.value.code == "EVENT_HASH_MISMATCH"
    assert ledger.snapshot() == before
    assert ledger.get(tampered.event_hash) is None
    assert ledger.get(event.event_hash) == event
