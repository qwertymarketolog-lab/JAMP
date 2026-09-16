"""EXP-10 / R0.5 contract tests for the append-only causal ledger."""

from dataclasses import replace

import pytest

from jamp.research.causal_ledger import (
    ZERO_HASH,
    CausalLedger,
    CausalOrderViolationError,
    DuplicateEventError,
    EventHashMismatchError,
    EventTypeV0,
    EvidenceDuplicateError,
    ExecutionIdDuplicateError,
    ExecutionResultDuplicateError,
    ExecutionResultMissingError,
    ExecutionStartMissingError,
    GenesisViolationError,
    HeadViolationError,
    LedgerError,
    ParentMissingError,
    PayloadHashMismatchError,
    PredictionCommitMissingError,
    SequenceDiscontinuityError,
)

_HASH = "1" * 64
_RESULT_REF = "2" * 64
_EVIDENCE_REF = "3" * 64
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
    payload = {"execution_id": "exec-a", "prediction_commit_hash": _HASH}
    event = _event(ledger, EventTypeV0.EXECUTION_START, payload=payload)
    _assert_rejected_without_mutation(ledger, event, payload, PredictionCommitMissingError)


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
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {
        "execution_id": "exec-a",
        "prediction_commit_hash": genesis.event_hash,
    }
    event = _event(
        ledger,
        EventTypeV0.EXECUTION_START,
        parent_hash=genesis.event_hash,
        sequence_index=2,
        payload=payload,
    )
    assert prediction.event_hash == ledger.head
    _assert_rejected_without_mutation(ledger, event, payload, HeadViolationError)


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


def test_j_execution_start_binds_to_prediction_commit() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    event = ledger.append_execution_start(prediction.event_hash, "exec-a")
    assert event.event_type is EventTypeV0.EXECUTION_START
    assert event.parent_hash == prediction.event_hash
    assert event.sequence_index == 2
    assert ledger.head == event.event_hash
    assert ledger.event_count == 3


def test_k_execution_start_without_prediction_commit_is_rejected_atomically() -> None:
    ledger = _ledger()
    payload = {"execution_id": "exec-a", "prediction_commit_hash": ledger.head}
    event = _event(ledger, EventTypeV0.EXECUTION_START, payload=payload)
    _assert_rejected_without_mutation(ledger, event, payload, PredictionCommitMissingError)


def test_l_execution_start_wrong_prediction_commit_reference_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": "2" * 64}
    event = _event(ledger, EventTypeV0.EXECUTION_START, payload=payload)
    assert event.parent_hash == prediction.event_hash
    _assert_rejected_without_mutation(ledger, event, payload, PredictionCommitMissingError)


def test_m_duplicate_execution_id_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    ledger.append_execution_start(prediction.event_hash, "exec-a")
    before = ledger.snapshot()
    with pytest.raises(ExecutionIdDuplicateError):
        ledger.append_execution_start(prediction.event_hash, "exec-a")
    assert ledger.snapshot() == before


def test_n_execution_start_payload_hash_mismatch_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": prediction.event_hash}
    event = ledger.build_event(EventTypeV0.EXECUTION_START, 2, prediction.event_hash, payload)
    forged_payload = {"execution_id": "exec-b", "prediction_commit_hash": prediction.event_hash}
    _assert_rejected_without_mutation(ledger, event, forged_payload, PayloadHashMismatchError)


def test_o_execution_start_event_hash_mismatch_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": prediction.event_hash}
    event = ledger.build_event(EventTypeV0.EXECUTION_START, 2, prediction.event_hash, payload)
    forged = replace(event, event_hash="4" * 64)
    _assert_rejected_without_mutation(ledger, forged, payload, EventHashMismatchError)


def test_p_execution_start_sequence_gap_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": prediction.event_hash}
    event = ledger.build_event(EventTypeV0.EXECUTION_START, 7, prediction.event_hash, payload)
    _assert_rejected_without_mutation(ledger, event, payload, SequenceDiscontinuityError)


def test_q_execution_start_old_parent_is_rejected_atomically() -> None:
    ledger = _ledger()
    genesis = ledger.genesis()
    ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": genesis.event_hash}
    event = ledger.build_event(EventTypeV0.EXECUTION_START, 2, genesis.event_hash, payload)
    _assert_rejected_without_mutation(ledger, event, payload, HeadViolationError)


def test_r_execution_start_rejection_preserves_ledger_state() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_id": "exec-a", "prediction_commit_hash": "2" * 64}
    event = ledger.build_event(EventTypeV0.EXECUTION_START, 2, prediction.event_hash, payload)
    before = ledger.snapshot()
    with pytest.raises(PredictionCommitMissingError):
        ledger.append(event, payload=payload)
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None


def _execution_start() -> tuple[CausalLedger, object]:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    execution_start = ledger.append_execution_start(prediction.event_hash, "exec-a")
    return ledger, execution_start


def test_s_execution_result_binds_to_execution_start() -> None:
    ledger, execution_start = _execution_start()
    event = ledger.append_execution_result(execution_start.event_hash, _RESULT_REF)
    assert event.event_type is EventTypeV0.EXECUTION_RESULT
    assert event.parent_hash == execution_start.event_hash
    assert event.sequence_index == 3
    assert ledger.head == event.event_hash
    assert ledger.event_count == 4


def test_t_execution_result_without_execution_start_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_start_hash": prediction.event_hash, "result_ref": _RESULT_REF}
    event = _event(ledger, EventTypeV0.EXECUTION_RESULT, payload=payload)
    _assert_rejected_without_mutation(ledger, event, payload, ExecutionStartMissingError)


def test_u_execution_result_wrong_execution_start_reference_is_rejected_atomically() -> None:
    ledger, execution_start = _execution_start()
    payload = {"execution_start_hash": "3" * 64, "result_ref": _RESULT_REF}
    event = _event(ledger, EventTypeV0.EXECUTION_RESULT, payload=payload)
    assert event.parent_hash == execution_start.event_hash
    _assert_rejected_without_mutation(ledger, event, payload, ExecutionStartMissingError)


def test_v_duplicate_execution_result_is_rejected_atomically() -> None:
    ledger, execution_start = _execution_start()
    ledger.append_execution_result(execution_start.event_hash, _RESULT_REF)
    before = ledger.snapshot()
    with pytest.raises(ExecutionResultDuplicateError):
        ledger.append_execution_result(execution_start.event_hash, _RESULT_REF)
    assert ledger.snapshot() == before


def test_w_execution_result_payload_hash_mismatch_is_rejected_atomically() -> None:
    ledger, execution_start = _execution_start()
    payload = {"execution_start_hash": execution_start.event_hash, "result_ref": _RESULT_REF}
    event = ledger.build_event(EventTypeV0.EXECUTION_RESULT, 3, execution_start.event_hash, payload)
    forged_payload = {"execution_start_hash": execution_start.event_hash, "result_ref": "4" * 64}
    _assert_rejected_without_mutation(ledger, event, forged_payload, PayloadHashMismatchError)


def test_x_execution_result_event_hash_mismatch_is_rejected_atomically() -> None:
    ledger, execution_start = _execution_start()
    payload = {"execution_start_hash": execution_start.event_hash, "result_ref": _RESULT_REF}
    event = ledger.build_event(EventTypeV0.EXECUTION_RESULT, 3, execution_start.event_hash, payload)
    forged = replace(event, event_hash="5" * 64)
    _assert_rejected_without_mutation(ledger, forged, payload, EventHashMismatchError)


def test_y_execution_result_sequence_gap_is_rejected_atomically() -> None:
    ledger, execution_start = _execution_start()
    payload = {"execution_start_hash": execution_start.event_hash, "result_ref": _RESULT_REF}
    event = ledger.build_event(EventTypeV0.EXECUTION_RESULT, 8, execution_start.event_hash, payload)
    _assert_rejected_without_mutation(ledger, event, payload, SequenceDiscontinuityError)


def test_z_execution_result_old_parent_is_rejected_atomically() -> None:
    ledger, execution_start = _execution_start()
    genesis = ledger.genesis()
    payload = {"execution_start_hash": genesis.event_hash, "result_ref": _RESULT_REF}
    event = ledger.build_event(EventTypeV0.EXECUTION_RESULT, 3, genesis.event_hash, payload)
    assert execution_start.event_hash == ledger.head
    _assert_rejected_without_mutation(ledger, event, payload, HeadViolationError)


def _execution_result() -> tuple[CausalLedger, object]:
    ledger, execution_start = _execution_start()
    execution_result = ledger.append_execution_result(execution_start.event_hash, _RESULT_REF)
    return ledger, execution_result


def test_aa_evidence_record_binds_to_execution_result() -> None:
    ledger, execution_result = _execution_result()
    event = ledger.append_evidence_record(execution_result.event_hash, _EVIDENCE_REF)
    assert event.event_type is EventTypeV0.EVIDENCE_RECORD
    assert event.parent_hash == execution_result.event_hash
    assert event.sequence_index == 4
    assert ledger.head == event.event_hash
    assert ledger.event_count == 5


def test_ab_evidence_without_execution_result_is_rejected_atomically() -> None:
    ledger = _ledger()
    prediction = ledger.append_prediction_commit(_HASH)
    payload = {"execution_result_hash": prediction.event_hash, "evidence_ref": _EVIDENCE_REF}
    event = _event(ledger, EventTypeV0.EVIDENCE_RECORD, payload=payload)
    _assert_rejected_without_mutation(ledger, event, payload, ExecutionResultMissingError)


def test_ac_missing_execution_result_reference_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    payload = {"execution_result_hash": "4" * 64, "evidence_ref": _EVIDENCE_REF}
    event = _event(ledger, EventTypeV0.EVIDENCE_RECORD, payload=payload)
    assert event.parent_hash == execution_result.event_hash
    _assert_rejected_without_mutation(ledger, event, payload, ExecutionResultMissingError)


def test_ad_wrong_execution_result_reference_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    payload = {"execution_result_hash": "5" * 64, "evidence_ref": _EVIDENCE_REF}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        4,
        execution_result.event_hash,
        payload,
    )
    _assert_rejected_without_mutation(ledger, event, payload, ExecutionResultMissingError)


def test_ae_duplicate_evidence_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    ledger.append_evidence_record(execution_result.event_hash, _EVIDENCE_REF)
    before = ledger.snapshot()
    with pytest.raises(EvidenceDuplicateError):
        ledger.append_evidence_record(execution_result.event_hash, _EVIDENCE_REF)
    assert ledger.snapshot() == before


def test_af_evidence_payload_hash_mismatch_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    payload = {"execution_result_hash": execution_result.event_hash, "evidence_ref": _EVIDENCE_REF}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        4,
        execution_result.event_hash,
        payload,
    )
    forged_payload = {
        "execution_result_hash": execution_result.event_hash,
        "evidence_ref": "6" * 64,
    }
    _assert_rejected_without_mutation(ledger, event, forged_payload, PayloadHashMismatchError)


def test_ag_evidence_event_hash_mismatch_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    payload = {"execution_result_hash": execution_result.event_hash, "evidence_ref": _EVIDENCE_REF}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        4,
        execution_result.event_hash,
        payload,
    )
    forged = replace(event, event_hash="7" * 64)
    _assert_rejected_without_mutation(ledger, forged, payload, EventHashMismatchError)


def test_ah_evidence_sequence_gap_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    payload = {"execution_result_hash": execution_result.event_hash, "evidence_ref": _EVIDENCE_REF}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        9,
        execution_result.event_hash,
        payload,
    )
    _assert_rejected_without_mutation(ledger, event, payload, SequenceDiscontinuityError)


def test_ai_evidence_old_parent_is_rejected_atomically() -> None:
    ledger, execution_result = _execution_result()
    prediction = ledger.get(ledger.genesis().event_hash)
    assert prediction is not None
    payload = {"execution_result_hash": prediction.event_hash, "evidence_ref": _EVIDENCE_REF}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        4,
        prediction.event_hash,
        payload,
    )
    assert execution_result.event_hash == ledger.head
    _assert_rejected_without_mutation(ledger, event, payload, HeadViolationError)


def test_aj_evidence_rejection_preserves_ledger_state() -> None:
    ledger, execution_result = _execution_result()
    payload = {"execution_result_hash": "8" * 64, "evidence_ref": _EVIDENCE_REF}
    event = ledger.build_event(
        EventTypeV0.EVIDENCE_RECORD,
        4,
        execution_result.event_hash,
        payload,
    )
    before = ledger.snapshot()
    with pytest.raises(ExecutionResultMissingError):
        ledger.append(event, payload=payload)
    assert ledger.snapshot() == before
    assert ledger.get(event.event_hash) is None
