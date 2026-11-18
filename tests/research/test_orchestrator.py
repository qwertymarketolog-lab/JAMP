from __future__ import annotations

import asyncio

import pytest

from jamp.runtime.orchestrator import MultiModelOrchestrator


class FakeExecutor:
    def execute(self, model, messages, max_tokens):
        if model == "provider/model-fail":
            raise TimeoutError("simulated provider timeout")
        return {
            "raw_body": '{"choices":[]}',
            "raw_body_sha256": "a" * 64,
            "model_id": model,
            "provider_response_id": f"response-{model}",
            "content": f"answer from {model}",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "cost_estimate_rub": "0.25",
            "error": None,
        }


def test_three_models_keep_two_successes_and_one_failure_with_partial_cost() -> None:
    orchestrator = MultiModelOrchestrator(FakeExecutor())
    result = asyncio.run(orchestrator.execute(
        "same prompt for all",
        ["provider/model-a", "provider/model-fail", "provider/model-c"],
        max_tokens=128,
        run_id="run-123",
    ))

    assert len(result["results"]) == 3
    assert [item["model"] for item in result["results"]] == [
        "provider/model-a", "provider/model-fail", "provider/model-c"
    ]
    assert result["results"][0]["response"]["content"] == "answer from provider/model-a"
    assert result["results"][0]["trace_id"] == "run-123_provider-model-a"
    assert result["results"][1]["response"] is None
    assert result["results"][1]["error"]["type"] == "TimeoutError"
    assert result["results"][2]["response"]["content"] == "answer from provider/model-c"
    assert result["total_cost_rub"] == "PARTIAL"


def test_one_timeout_does_not_discard_other_four_results() -> None:
    models = [
        "provider/model-a",
        "provider/model-b",
        "provider/model-timeout",
        "provider/model-d",
        "provider/model-e",
    ]

    class OneTimeoutExecutor:
        async def execute(self, model, messages, max_tokens):
            await asyncio.sleep(0)
            if model == "provider/model-timeout":
                raise TimeoutError("one model timed out")
            return {
                "raw_body": "{}",
                "raw_body_sha256": "b" * 64,
                "model_id": model,
                "content": f"answer from {model}",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "cost_estimate_rub": "0.01",
                "error": None,
            }

    result = asyncio.run(MultiModelOrchestrator(OneTimeoutExecutor()).execute(
        "one shared prompt", models, max_tokens=64, run_id="run-five"
    ))

    assert len(result["results"]) == 5
    assert sum(item["error"] is None for item in result["results"]) == 4
    assert sum(item["error"] is not None for item in result["results"]) == 1
    assert result["results"][2]["trace_id"] == "run-five_provider-model-timeout"
    assert result["total_cost_rub"] == "PARTIAL"


def test_total_cost_is_sum_only_when_every_model_cost_is_known() -> None:
    class KnownCosts:
        def execute(self, model, messages, max_tokens):
            return {
                "raw_body": "{}",
                "raw_body_sha256": "c" * 64,
                "model_id": model,
                "content": "ok",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "cost_estimate_rub": "0.10",
                "error": None,
            }

    result = asyncio.run(MultiModelOrchestrator(KnownCosts()).execute(
        "prompt", ["model-a", "model-b"], max_tokens=32, run_id="run-cost"
    ))
    assert result["total_cost_rub"] == "0.20"


def test_orchestrator_rejects_duplicate_models_and_bad_request() -> None:
    orchestrator = MultiModelOrchestrator(FakeExecutor())
    with pytest.raises(ValueError, match="unique"):
        asyncio.run(orchestrator.execute("prompt", ["same", "same"], max_tokens=32))
    with pytest.raises(ValueError, match="prompt"):
        asyncio.run(orchestrator.execute("", ["model-a"], max_tokens=32))
