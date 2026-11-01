import base64
import io
import json
import sys
import wave
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from tools.video_probe import run_video_probe as probe


def make_bundle(
    path: Path,
    *,
    frame_count: int = 5,
    channels: int = 1,
    sample_width: int = 2,
    sample_rate: int = 16000,
    seconds: int = 31,
) -> Path:
    audio_path = path.parent / "audio_16k_mono.wav"
    with wave.open(str(audio_path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(sample_width)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00" * sample_rate * seconds * channels * sample_width)

    with zipfile.ZipFile(path, "w") as bundle:
        for index in range(frame_count):
            bundle.writestr(f"frames/frame_{index:02}.jpg", f"frame-{index}".encode())
        bundle.write(audio_path, "audio/audio_16k_mono.wav")
    return path


def test_extract_safe_extracts_members_under_root(tmp_path):
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("frames/frame_00.jpg", b"frame")
    destination = tmp_path / "extracted"

    probe.extract_safe(bundle, destination)

    assert (destination / "frames/frame_00.jpg").read_bytes() == b"frame"


@pytest.mark.parametrize("member_name", ["../escape.txt", "/absolute.txt"])
def test_extract_safe_rejects_traversal_paths(tmp_path, member_name):
    bundle = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr(member_name, b"unsafe")

    with pytest.raises(ValueError, match="unsafe zip member path"):
        probe.extract_safe(bundle, tmp_path / "extracted")

    assert not (tmp_path / "escape.txt").exists()


def test_extract_safe_rejects_more_than_100_members(tmp_path):
    bundle = tmp_path / "too-many.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        for index in range(101):
            archive.writestr(f"{index}.txt", b"x")

    with pytest.raises(ValueError, match="too many members"):
        probe.extract_safe(bundle, tmp_path / "extracted")


def test_media_from_bundle_requires_exactly_five_frames(tmp_path):
    bundle = make_bundle(tmp_path / "bundle.zip", frame_count=4)

    with pytest.raises(ValueError, match="exactly five frames"):
        probe.media_from_bundle(bundle, tmp_path / "extracted")


@pytest.mark.parametrize(
    ("channels", "sample_width", "sample_rate"),
    [(2, 2, 16000), (1, 1, 16000), (1, 2, 44100)],
)
def test_media_from_bundle_rejects_noncanonical_audio(
    tmp_path, channels, sample_width, sample_rate
):
    bundle = make_bundle(
        tmp_path / "bundle.zip",
        channels=channels,
        sample_width=sample_width,
        sample_rate=sample_rate,
    )

    with pytest.raises(ValueError, match="mono 16kHz PCM16"):
        probe.media_from_bundle(bundle, tmp_path / "extracted")


def test_media_from_bundle_limits_audio_excerpt_to_30_seconds(tmp_path):
    bundle = make_bundle(tmp_path / "bundle.zip", seconds=35)

    frames, audio_bytes, metadata = probe.media_from_bundle(
        bundle, tmp_path / "extracted"
    )

    assert len(frames) == 5
    assert metadata["audio_excerpt"]["duration_seconds"] == 30
    with wave.open(io.BytesIO(audio_bytes), "rb") as excerpt:
        assert excerpt.getnchannels() == 1
        assert excerpt.getsampwidth() == 2
        assert excerpt.getframerate() == 16000
        assert excerpt.getnframes() == 16000 * 30


def test_redact_request_removes_image_and_audio_payloads():
    image = b"image-bytes"
    audio = b"audio-bytes"
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,"
                            + base64.b64encode(image).decode()
                        },
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(audio).decode(),
                            "format": "wav",
                        },
                    },
                ],
            }
        ]
    }

    redacted = probe.redact_request(json.dumps(payload).encode())
    content = redacted["messages"][0]["content"]

    assert content[0]["image_url"] == {
        "data_redacted": True,
        "sha256": probe.digest(image),
        "bytes": len(image),
    }
    assert content[1]["input_audio"] == {
        "data_redacted": True,
        "sha256": probe.digest(audio),
        "bytes": len(audio),
        "format": "wav",
    }
    assert image.decode() not in json.dumps(redacted)
    assert audio.decode() not in json.dumps(redacted)


class FakeResponse:
    status = 200
    headers = {"x-request-id": "request-123"}

    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.body


def test_provider_call_records_actual_model_and_redacted_request(monkeypatch):
    image = b"private-image"
    response = {
        "id": "response-123",
        "model": "provider/actual-model",
        "choices": [{"message": {"content": "observed"}}],
        "usage": {"total_tokens": 7},
    }
    monkeypatch.setattr(
        probe,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(json.dumps(response).encode()),
    )
    content = [
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/jpeg;base64,"
                + base64.b64encode(image).decode()
            },
        }
    ]

    result = probe.provider_call(
        "test-provider",
        "https://provider.example/v1/chat/completions",
        "test-secret",
        "requested/model",
        "sampled_frames",
        content,
    )

    assert result["outcome"] == "HTTP_2XX_COMPLETION_PRESENT"
    assert result["http_status"] == 200
    assert result["requested_model_id"] == "requested/model"
    assert result["actual_model_id"] == "provider/actual-model"
    assert result["response_id"] == "response-123"
    assert result["response_request_id"] == "request-123"
    assert result["request_redacted"]["messages"][0]["content"][0]["image_url"][
        "data_redacted"
    ] is True
    assert image.decode() not in json.dumps(result["request_redacted"])


def test_provider_call_captures_http_error_without_claiming_completion(monkeypatch):
    error_body = b'{"error":{"message":"unsupported modality"}}'

    def raise_http_error(*_args, **_kwargs):
        raise HTTPError(
            "https://provider.example",
            422,
            "Unprocessable Entity",
            {"x-request-id": "request-error"},
            io.BytesIO(error_body),
        )

    monkeypatch.setattr(probe, "urlopen", raise_http_error)
    result = probe.provider_call(
        "test-provider",
        "https://provider.example/v1/chat/completions",
        "test-secret",
        "requested/model",
        "audio_excerpt",
        [{"type": "text", "text": "transcribe"}],
    )

    assert result["outcome"] == "HTTP_ERROR"
    assert result["http_status"] == 422
    assert result["response_request_id"] == "request-error"
    assert "unsupported modality" in result["raw_response_body"]


def test_provider_call_records_transport_error(monkeypatch):
    def raise_transport_error(*_args, **_kwargs):
        raise URLError("connection refused")

    monkeypatch.setattr(probe, "urlopen", raise_transport_error)
    result = probe.provider_call(
        "test-provider",
        "https://provider.example/v1/chat/completions",
        "test-secret",
        "requested/model",
        "sampled_frames",
        [{"type": "text", "text": "describe"}],
    )

    assert result["outcome"] == "TRANSPORT_ERROR"
    assert result["error_type"] == "URLError"
    assert "http_status" not in result


def test_anymodel_transcription_records_transcript_and_audio_digest(monkeypatch):
    captured = {}

    def fake_urlopen(request, **_kwargs):
        captured["request"] = request
        return FakeResponse(b'{"text":"recognized words","model":"actual-stt"}')

    monkeypatch.setattr(probe, "urlopen", fake_urlopen)
    audio = b"wav-audio-content"

    result = probe.anymodel_transcription_call(
        "https://anymodel.example/v1/audio/transcriptions",
        "test-secret",
        "requested-stt",
        audio,
    )

    assert result["outcome"] == "HTTP_2XX_TRANSCRIPTION_PRESENT"
    assert result["http_status"] == 200
    assert result["actual_model_id"] == "actual-stt"
    assert result["request_redacted"]["file"]["sha256"] == probe.digest(audio)
    assert result["request_redacted"]["file"]["data_redacted"] is True
    assert captured["request"].get_header("Content-type").startswith(
        "multipart/form-data; boundary="
    )
    assert audio in captured["request"].data
    assert base64.b64encode(audio) not in json.dumps(result["request_redacted"]).encode()
    assert audio.decode() not in json.dumps(result["request_redacted"])


def test_main_writes_observation_only_evidence_and_summary(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path / "bundle.zip")
    output = tmp_path / "evidence"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_video_probe.py",
            "--bundle",
            str(bundle),
            "--output",
            str(output),
            "--anymodel-vision-model",
            "am/vision",
            "--anymodel-audio-model",
            "am/audio",
            "--openrouter-vision-model",
            "or/vision",
            "--openrouter-audio-model",
            "or/audio",
        ],
    )
    monkeypatch.setenv("ANYMODEL_API_KEY", "anymodel-secret")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret")
    monkeypatch.setattr(
        probe,
        "jamp_runtime",
        lambda *_args: {"test": "JAMP_RUNTIME", "outcome": "HTTP_RESPONSE_CAPTURED"},
    )
    monkeypatch.setattr(
        probe,
        "provider_call",
        lambda provider, _endpoint, _key, model, modality, _content: {
            "provider": provider,
            "requested_model_id": model,
            "modality": modality,
            "outcome": "HTTP_2XX_COMPLETION_PRESENT",
        },
    )
    monkeypatch.setattr(
        probe,
        "anymodel_transcription_call",
        lambda _endpoint, _key, model, _audio: {
            "provider": "anymodel",
            "requested_model_id": model,
            "modality": "audio_transcription",
            "outcome": "HTTP_2XX_TRANSCRIPTION_PRESENT",
        },
    )

    assert probe.main() == 0

    evidence = json.loads((output / "evidence.json").read_text(encoding="utf-8"))
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert evidence["qualification"] == "NOT_EVALUATED"
    assert evidence["test_count"] == 5
    assert evidence["provider_success_count"] == 4
    assert "Qualification: NOT_EVALUATED" in summary
    assert "NOT_EVALUATED" in summary
