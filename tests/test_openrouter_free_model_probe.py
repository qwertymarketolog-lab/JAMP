from __future__ import annotations

import json

from scripts.research import openrouter_probe_free_models as probe


def test_probe_model_records_success_without_generated_text_or_secret(monkeypatch):
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {
                    "id": "response-123",
                    "model": "provider/model:free",
                    "choices": [{"message": {"content": "OK, private generated text"}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 1},
                }
            ).encode("utf-8")

    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "CHAT_COMPLETION_OK"
    assert result["http_status"] == 200
    assert result["provider_response_id"] == "response-123"
    assert result["usage"]["completion_tokens"] == 1
    assert seen["url"] == probe.CHAT_URL
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["payload"]["model"] == "provider/model:free"
    assert seen["payload"]["max_tokens"] == 8
    assert "test-secret" not in repr(result)
    assert "private generated text" not in repr(result)


def test_probe_model_does_not_store_provider_error_body(monkeypatch):
    from urllib.error import HTTPError
    from io import BytesIO

    def fake_urlopen(request, timeout):
        raise HTTPError(
            probe.CHAT_URL,
            429,
            "rate limited",
            hdrs=None,
            fp=BytesIO(b'{"error":"sensitive provider detail"}'),
        )

    monkeypatch.setattr(probe.urllib.request, "urlopen", fake_urlopen)
    result = probe.probe_model("test-secret", "provider/model:free", 4)

    assert result["status"] == "HTTP_ERROR"
    assert result["http_status"] == 429
    assert "sensitive provider detail" not in repr(result)
    assert "test-secret" not in repr(result)


def test_text_output_requires_explicit_text_modality():
    assert probe.is_text_output({"architecture": {"output_modalities": ["text"]}})
    assert not probe.is_text_output({"architecture": {"output_modalities": ["audio"]}})
    assert not probe.is_text_output({"architecture": {}})
