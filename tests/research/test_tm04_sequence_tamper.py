"""EXP-11 / TM-04 sequence-index tamper tests."""

import pytest

from jamp.research.causal_ledger import (
    CausalLedger,
    EventTypeV0,
    SequenceDiscontinuityError,
)

_HASH = "1" * 64


def _ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    ledger.append_prediction_commit(_HASH)
    return ledger


def _assert_sequence_tamper_rejected(sequence_index: int) -> None:
    ledger = _ledger()
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = ledger.build_event(
        EventTypeV0.EXECUTION_START,
        sequence_index,
        ledger.head,
        payload,
    )
    before = ledger.snapshot()

    with pytest.raises(SequenceDiscontinuityError) as exc_info:
        ledger.append(event, payload=payload)

    after = ledger.snapshot()
    assert exc_info.value.code == SequenceDiscontinuityError.code
    assert after == before
    assert ledger.get(event.event_hash) is None


@pytest.mark.parametrize(
    ("attack", "sequence_index"),
    [
        ("skip", 3),
        ("duplicate", 1),
        ("rollback", 0),
    ],
)
def test_tm04_sequence_index_tamper_is_rejected_atomically(
    attack: str, sequence_index: int
) -> None:
    """TM-04: skip, duplicate, and rollback preserve L0 ledger state."""
    _assert_sequence_tamper_rejected(sequence_index)
