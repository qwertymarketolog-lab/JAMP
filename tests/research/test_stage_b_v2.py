from __future__ import annotations

from scripts.research.stage_b_v2_targeted import (
    BLOCKED,
    TARGETS,
    classify,
    parse_coefficient,
    resolve_coefficients,
    valid_number,
)


def test_exactly_four_targets():
    assert len(TARGETS) == 4
    assert [(t["model_id"], t["task_id"], t["max_tokens"]) for t in TARGETS] == [
        ("am/nemotron-3-ultra-550b-a55b", "task5", 4096),
        ("ds/deepseek-v4-pro", "task1", 8192),
        ("ds/deepseek-v4-pro", "task2", 8192),
        ("ds/deepseek-v4-pro", "task5", 8192),
    ]


def test_astra_task2_is_blocked_and_not_targeted():
    assert any(b["model_id"] == "cx/gpt-6-astra" and b["task_id"] == "task2" for b in BLOCKED)
    assert all(not (t["model_id"] == "cx/gpt-6-astra" and t["task_id"] == "task2") for t in TARGETS)


def test_target_max_tokens_are_exact():
    assert TARGETS[0]["max_tokens"] == 4096
    assert all(t["max_tokens"] == 8192 for t in TARGETS[1:])


def test_parse_scalar_coefficient():
    assert parse_coefficient({"coefficient": 4}) == (4.0, 4.0)


def test_parse_split_coefficients():
    assert parse_coefficient({"coefficient": {"input": 0.5, "output": 0.75}}) == (0.5, 0.75)


def test_reject_invalid_coefficients():
    assert parse_coefficient({}) is None
    assert parse_coefficient({"coefficient": True}) is None
    assert parse_coefficient({"coefficient": -1}) is None
    assert parse_coefficient({"coefficient": float("nan")}) is None
    assert parse_coefficient({"coefficient": {"input": 1, "output": float("inf")}}) is None


def test_valid_number_rejects_bool_and_nonfinite():
    assert valid_number(0)
    assert not valid_number(True)
    assert not valid_number(float("inf"))


def test_resolve_requires_exactly_one_catalog_match():
    row = {"id": "ds/deepseek-v4-pro", "billing": {"coefficient": 0.5}}
    assert resolve_coefficients({"data": [row]}, row["id"]) == (0.5, 0.5)
    assert resolve_coefficients({"data": [row, row]}, row["id"]) is None
    assert resolve_coefficients({"data": []}, row["id"]) is None


def test_classify_complete():
    body = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    assert classify(200, body) == "RESPONSE_COMPLETE"


def test_classify_empty_even_when_finish_length():
    body = {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
    assert classify(200, body) == "RESPONSE_EMPTY"


def test_classify_truncated():
    body = {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}
    assert classify(200, body) == "RESPONSE_TRUNCATED"


def test_classify_incomplete_finish_reason():
    body = {"choices": [{"message": {"content": "text"}, "finish_reason": "tool_calls"}]}
    assert classify(200, body) == "RESPONSE_INCOMPLETE"


def test_classify_http_error():
    assert classify(500, {}) == "HTTP_500"
