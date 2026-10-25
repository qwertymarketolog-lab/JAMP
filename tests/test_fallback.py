from __future__ import annotations

import pytest

from jamp.provider.fallback import FallbackChainExecutor


class FakeExecutor:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = 0

    def __call__(self, selected_model, payload):
        self.calls += 1
        if self.error:
            raise self.error
        return dict(self.result or {})


def test_first_provider_success_has_empty_history():
    first = FakeExecutor({"provider": "first", "content": "ok"})
    chain = FallbackChainExecutor([first])
    result = chain("model-a", {"prompt": "hello"})
    assert result["provider"] == "first"
    assert result["fallback_history"] == []
    assert first.calls == 1


def test_fallback_records_first_provider_502():
    first = FakeExecutor(error=RuntimeError("HTTP 502 upstream unavailable"))
    second = FakeExecutor({"provider": "second", "content": "ok"})
    result = FallbackChainExecutor([first, second])("model-a", {"prompt": "hello"})
    assert result["provider"] == "second"
    assert result["fallback_history"] == [
        {
            "provider": "FakeExecutor",
            "requested_model": "model-a",
            "http_status": 502,
            "error": "HTTP 502 upstream unavailable",
        }
    ]


def test_all_failures_raise_with_bounded_history():
    first = FakeExecutor(error=RuntimeError("HTTP 402 payment required"))
    second = FakeExecutor(error=RuntimeError("HTTP 404 model missing"))
    chain = FallbackChainExecutor([first, second])
    with pytest.raises(RuntimeError, match="All fallback providers failed") as raised:
        chain("model-a", {"prompt": "hello"})
    assert [entry["http_status"] for entry in raised.value.fallback_history] == [402, 404]


def test_attempts_are_capped_at_five_and_error_is_redacted():
    executors = [FakeExecutor(error=RuntimeError("Bearer supersecret HTTP 503")) for _ in range(7)]
    chain = FallbackChainExecutor(executors, max_attempts=99)
    with pytest.raises(RuntimeError) as raised:
        chain("model-a", {"prompt": "hello"})
    history = raised.value.fallback_history
    assert len(history) == 5
    assert all("supersecret" not in entry["error"] for entry in history)
