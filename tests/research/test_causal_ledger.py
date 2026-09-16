"""EXP-10 / R0.2 contract tests for the append-only causal ledger."""

from dataclasses import replace

import pytest

from jamp.research.causal_ledger import (
    ZERO_HASH,
    CausalLedger,
    CausalOrderViolationError,
    DuplicateEventError,
    EventHashMismatchError,
    EventTypeV0,
    GenesisViolationError,
    HeadViolationError,
    LedgerError,
    ParentMissingError,
    PayloadHashMismatchError,
    SequenceDiscontinuityError,
)

_HASH = "1" * 64
_PAYLOAD = {"prediction_hash": _HASH}


def _ledger() -> CausalLedger:
    ledger = CausalLedger()
    ledger.append_genesis()
    return ledger


def _event(
    ledger: CausalLedger,
    event_type: EventTypeV0,
    *,
    parent_hash: str | None = None,
    sequence_index: int | None = None,
    payload: dict[str, str] | None = None,
):
    return ledger.build_event(
        event_type,
        ledger.event_count if sequence_index is None else sequence_index,
        ledger.head if parent_hash is None else parent_hash,
        _PAYLOAD if payload is None else payload,
    )


def _assert_rejected_without_mutation(
    ledger: CausalLedger, event, payload, expected: type[LedgerError]
) -> None:
    before = ledger.snapshot()
    with pytest.raises(expected) as exc_info:
        ledger.append(event, payload=payload)
    after = ledger.snapshot()
    assert exc_info.value.code == expected.code
    assert after == before


def test_genesis_is_deterministic_and_uses_uniform_hash_type() -> None:
    first = CausalLedger.genesis()
    second = CausalLedger.genesis()
    assert first == second
    assert first.parent_hash == ZERO_HASH
    assert len(first.parent_hash) == 64
    assert first.sequence_index == 0
    assert first.verify_event_hash()


def test_prediction_commit_extends_genesis() -> None:
    ledger = _ledger()
    event = ledger.append_prediction_commit(_HASH)
    assert event.event_type is EventTypeV0.PREDICTION_COMMIT
    assert event.parent_hash == ledger.get(ledger.genesis().event_hash).event_hash
    assert event.sequence_index == 1
    assert ledger.head == event.event_hash
    assert ledger.event_count == 2


def test_a_evidence_without_execution_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.EVIDENCE_RECORD)
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, CausalOrderViolationError)


def test_b_execution_start_without_prediction_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.EXECUTION_START)
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, CausalOrderViolationError)


def test_c_missing_parent_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.PREDICTION_COMMIT, parent_hash="2" * 64)
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, ParentMissingError)


def test_d_payload_hash_mismatch_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.PREDICTION_COMMIT)
    _assert_rejected_without_mutation(
        ledger, event, {"prediction_hash": "3" * 64}, PayloadHashMismatchError
    )


def test_e_event_hash_mismatch_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.PREDICTION_COMMIT)
    forged = replace(event, event_hash="4" * 64)
    _assert_rejected_without_mutation(ledger, forged, _PAYLOAD, EventHashMismatchError)


def test_f_sequence_gap_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.PREDICTION_COMMIT, sequence_index=7)
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, SequenceDiscontinuityError)


def test_g_old_head_is_rejected_atomically() -> None:
    ledger = _ledger()
    genesis = ledger.genesis()
    ledger.append_prediction_commit(_HASH)
    event = _event(
        ledger,
        EventTypeV0.EXECUTION_START,
        parent_hash=genesis.event_hash,
        sequence_index=2,
    )
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, HeadViolationError)


def test_h_duplicate_event_is_rejected_atomically() -> None:
    ledger = _ledger()
    event = _event(ledger, EventTypeV0.PREDICTION_COMMIT)
    ledger.append(event, payload=_PAYLOAD)
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, DuplicateEventError)


def test_i_reordered_causal_event_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    event = _event(
        ledger,
        EventTypeV0.EVIDENCE_RECORD,
        parent_hash=prediction.event_hash,
        sequence_index=2,
    )
    _assert_rejected_without_mutation(ledger, event, _PAYLOAD, CausalOrderViolationError)


def test_genesis_cannot_be_reintroduced() -> None:
    ledger = _ledger()
    event = CausalLedger.build_event(EventTypeV0.GENESIS, 1, ledger.head, {})
    _assert_rejected_without_mutation(ledger, event, {}, GenesisViolationError)
