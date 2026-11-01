from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import tempfile
import time
import wave
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_safe(bundle: Path, root: Path) -> None:
    with zipfile.ZipFile(bundle) as archive:
        base = root.resolve()
        members = archive.infolist()
        if len(members) > 100:
            raise ValueError("archive has too many members")
        if sum(member.file_size for member in members) > 100 * 1024 * 1024:
            raise ValueError("archive expands beyond the 100 MiB limit")
        for member in members:
            name = PurePosixPath(member.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("unsafe zip member path")
            destination = (base / Path(*name.parts)).resolve()
            if destination != base and base not in destination.parents:
                raise ValueError("zip member escapes target")
        archive.extractall(base)


def media_from_bundle(
    bundle: Path, root: Path
) -> tuple[list[Path], bytes, dict[str, Any]]:
    extract_safe(bundle, root)
    frames = sorted(root.rglob("frame_*.jpg"))
    audio_paths = sorted(root.rglob("audio_16k_mono.wav"))
    if len(frames) != 5 or len(audio_paths) != 1:
        raise ValueError("bundle must contain exactly five frames and one canonical WAV")

    audio_path = audio_paths[0]
    with wave.open(str(audio_path), "rb") as source:
        params = source.getparams()
        if (params.nchannels, params.sampwidth, params.framerate) != (1, 2, 16000):
            raise ValueError("audio must be mono 16kHz PCM16")
        frame_count = min(params.nframes, params.framerate * 30)
        audio_pcm = source.readframes(frame_count)

    excerpt_path = root / "audio_excerpt_00_00_30.wav"
    with wave.open(str(excerpt_path), "wb") as excerpt:
        excerpt.setnchannels(1)
        excerpt.setsampwidth(2)
        excerpt.setframerate(16000)
        excerpt.writeframes(audio_pcm)
    audio_bytes = excerpt_path.read_bytes()

    metadata = {
        "frames": [
            {
                "name": frame.name,
                "sha256": digest(frame.read_bytes()),
                "bytes": frame.stat().st_size,
            }
            for frame in frames
        ],
        "audio_source": {
            "name": audio_path.name,
            "sha256": digest(audio_path.read_bytes()),
            "bytes": audio_path.stat().st_size,
        },
        "audio_excerpt": {
            "name": excerpt_path.name,
            "sha256": digest(audio_bytes),
            "bytes": len(audio_bytes),
            "start_seconds": 0,
            "duration_seconds": len(audio_pcm) / 32000,
            "sample_rate_hz": 16000,
            "channels": 1,
            "sample_format": "PCM16",
        },
    }
    return frames, audio_bytes, metadata


def redact_request(body: bytes) -> dict[str, Any]:
    payload = json.loads(body)
    for message in payload.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") == "image_url":
                image_url = part.get("image_url", {}).get("url", "")
                try:
                    raw = base64.b64decode(image_url.split(",", 1)[1], validate=True)
                except (IndexError, ValueError):
                    raw = b""
                part["image_url"] = {
                    "data_redacted": True,
                    "sha256": digest(raw),
                    "bytes": len(raw),
                }
            elif part.get("type") == "input_audio":
                encoded = part.get("input_audio", {}).get("data", "")
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except ValueError:
                    raw = b""
                part["input_audio"] = {
                    "data_redacted": True,
                    "sha256": digest(raw),
                    "bytes": len(raw),
                    "format": "wav",
                }
    return payload


def provider_call(
    provider: str,
    endpoint: str,
    api_key: str,
    model: str,
    modality: str,
    content: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": 256,
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    record: dict[str, Any] = {
        "provider": provider,
        "modality": modality,
        "requested_model_id": model,
        "endpoint_host": endpoint.split("/")[2],
        "request_started_at_utc": now(),
        "request_sha256": digest(body),
        "request_bytes": len(body),
        "request_redacted": redact_request(body),
    }
    request = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=120) as response:
            status = response.status
            raw = response.read()
            headers = response.headers
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        record.update(
            outcome="TRANSPORT_ERROR",
            error_type=type(exc).__name__,
            completed_at_utc=now(),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
        return record

    response_text = raw.decode("utf-8", errors="replace").replace(api_key, "[REDACTED]")
    try:
        decoded = json.loads(response_text)
    except json.JSONDecodeError:
        decoded = None
    choices = decoded.get("choices") if isinstance(decoded, dict) else None
    if 200 <= status < 300 and isinstance(choices, list) and choices:
        outcome = "HTTP_2XX_COMPLETION_PRESENT"
    elif 200 <= status < 300:
        outcome = "HTTP_2XX_RESPONSE_WITHOUT_COMPLETION"
    else:
        outcome = "HTTP_ERROR"

    record.update(
        outcome=outcome,
        http_status=status,
        completed_at_utc=now(),
        elapsed_seconds=round(time.monotonic() - started, 3),
        response_id=decoded.get("id") if isinstance(decoded, dict) else None,
        actual_model_id=decoded.get("model") if isinstance(decoded, dict) else None,
        usage=decoded.get("usage") if isinstance(decoded, dict) else None,
        response_request_id=headers.get("x-request-id") if headers else None,
        raw_response_body=response_text,
    )
    return record


def anymodel_transcription_call(
    endpoint: str, api_key: str, model: str, audio: bytes
) -> dict[str, Any]:
    boundary = "jamp-video-probe-" + digest(audio)[:20]
    parts = [
        (
            "--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="model"\r\n\r\n'
            + model + "\r\n"
        ).encode(),
        (
            "--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="file"; '
            'filename="audio_excerpt_00_00_30.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode(),
        audio,
        ("\r\n--" + boundary + "--\r\n").encode(),
    ]
    body = b"".join(parts)
    record: dict[str, Any] = {
        "provider": "anymodel",
        "modality": "audio_transcription",
        "requested_model_id": model,
        "endpoint_host": endpoint.split("/")[2],
        "request_started_at_utc": now(),
        "request_sha256": digest(body),
        "request_bytes": len(body),
        "request_redacted": {
            "model": model,
            "file": {
                "name": "audio_excerpt_00_00_30.wav",
                "content_type": "audio/wav",
                "sha256": digest(audio),
                "bytes": len(audio),
                "data_redacted": True,
            },
        },
    }
    request = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "multipart/form-data; boundary=" + boundary,
            "Accept": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=120) as response:
            status = response.status
            raw = response.read()
            headers = response.headers
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except (URLError, TimeoutError, OSError) as exc:
        record.update(
            outcome="TRANSPORT_ERROR",
            error_type=type(exc).__name__,
            completed_at_utc=now(),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
        return record

    response_text = raw.decode("utf-8", errors="replace").replace(api_key, "[REDACTED]")
    try:
        decoded = json.loads(response_text)
    except json.JSONDecodeError:
        decoded = None
    has_transcription = (
        isinstance(decoded, dict) and isinstance(decoded.get("text"), str)
    )
    if 200 <= status < 300 and has_transcription:
        outcome = "HTTP_2XX_TRANSCRIPTION_PRESENT"
    elif 200 <= status < 300:
        outcome = "HTTP_2XX_RESPONSE_WITHOUT_TRANSCRIPTION"
    else:
        outcome = "HTTP_ERROR"

    record.update(
        outcome=outcome,
        http_status=status,
        completed_at_utc=now(),
        elapsed_seconds=round(time.monotonic() - started, 3),
        actual_model_id=decoded.get("model") if isinstance(decoded, dict) else None,
        usage=decoded.get("usage") if isinstance(decoded, dict) else None,
        raw_response_body=response_text,
    )
    return record


def jamp_runtime(
    frames: list[Path], audio: bytes, output: Path
) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    from jamp.api.app import create_app
    from jamp.api.auth import OrganizationContext, require_api_key

    image_parts = [
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/jpeg;base64,"
                + base64.b64encode(frame.read_bytes()).decode()
            },
        }
        for frame in frames
    ]
    audio_part = {
        "type": "input_audio",
        "input_audio": {
            "data": base64.b64encode(audio).decode(),
            "format": "wav",
        },
    }
    payload = {
        "request_id": "video-probe-" + os.environ.get("GITHUB_RUN_ID", "local"),
        "intent": "search_and_extraction",
        "token_count": 1,
        "messages": [{"role": "user", "content": image_parts + [audio_part]}],
    }
    media_digest = {
        "frames": [digest(frame.read_bytes()) for frame in frames],
        "audio": digest(audio),
    }
    record: dict[str, Any] = {
        "test": "JAMP_RUNTIME",
        "input_modalities": ["sampled_frames", "audio_excerpt_0_30s"],
        "request_started_at_utc": now(),
        "media_digest": digest(json.dumps(media_digest, sort_keys=True).encode()),
    }
    try:
        os.environ["JAMP_API_KEY_HASH_SECRET"] = "video-probe-ephemeral-auth-secret"
        os.environ["JAMP_ENVIRONMENT"] = "local"
        app = create_app(audit_storage_path=output / "jamp-audit.jsonl")
        app.dependency_overrides[require_api_key] = lambda: OrganizationContext(
            org_id="video-probe",
            org_name="video-probe",
        )
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/v1/execute", json=payload)
            try:
                response_payload = response.json()
            except ValueError:
                response_payload = {}
            trace_id = response_payload.get("trace_id")
            if isinstance(trace_id, str) and trace_id:
                provenance_response = client.get("/v1/provenance/" + trace_id)
                record["provenance_http_status"] = provenance_response.status_code
                record["provenance_body"] = provenance_response.text
                record["trace_id"] = trace_id
        record.update(
            outcome="HTTP_RESPONSE_CAPTURED",
            http_status=response.status_code,
            response_body=response.text,
            completed_at_utc=now(),
        )
    except Exception as exc:
        record.update(
            outcome="RUNTIME_HARNESS_ERROR",
            error_type=type(exc).__name__,
            completed_at_utc=now(),
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--anymodel-vision-model", required=True)
    parser.add_argument("--anymodel-audio-model", required=True)
    parser.add_argument("--openrouter-vision-model", required=True)
    parser.add_argument("--openrouter-audio-model", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    evidence: dict[str, Any] = {
        "harness": "JAMP Video Probe Harness v0.1",
        "started_at_utc": now(),
        "qualification": "NOT_EVALUATED",
        "scope": (
            "five sampled frames plus first 30 seconds of audio; "
            "not full-video understanding"
        ),
        "bundle_sha256": digest(args.bundle.read_bytes()),
        "tests": [],
    }
    with tempfile.TemporaryDirectory(prefix="jamp-video-probe-") as temp:
        frames, audio, media = media_from_bundle(args.bundle, Path(temp))
        evidence["media"] = media
        evidence["tests"].append(jamp_runtime(frames, audio, args.output))

        images: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Analyze these sampled frames in timestamp order. "
                    "Describe only visible evidence."
                ),
            }
        ]
        for frame in frames:
            encoded = base64.b64encode(frame.read_bytes()).decode()
            images.append(
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + encoded},
                }
            )
        audio_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "Transcribe and summarize this 30-second audio excerpt.",
            },
            {
                "type": "input_audio",
                "input_audio": {
                    "data": base64.b64encode(audio).decode(),
                    "format": "wav",
                },
            },
        ]

        anymodel_key = os.environ.get("ANYMODEL_API_KEY", "")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        if anymodel_key:
            evidence["tests"].append(
                provider_call(
                    "anymodel",
                    os.environ.get(
                        "ANYMODEL_CHAT_URL", "https://anymodel.org/v1/chat/completions"
                    ),
                    anymodel_key,
                    args.anymodel_vision_model,
                    "sampled_frames",
                    images,
                )
            )
            evidence["tests"].append(
                anymodel_transcription_call(
                    os.environ.get(
                        "ANYMODEL_TRANSCRIPTION_URL",
                        "https://anymodel.org/v1/audio/transcriptions",
                    ),
                    anymodel_key,
                    args.anymodel_audio_model,
                    audio,
                )
            )
        else:
            evidence["tests"].extend(
                [
                    {
                        "provider": "anymodel",
                        "modality": "sampled_frames",
                        "requested_model_id": args.anymodel_vision_model,
                        "outcome": "SKIPPED_SECRET_MISSING",
                    },
                    {
                        "provider": "anymodel",
                        "modality": "audio_transcription",
                        "requested_model_id": args.anymodel_audio_model,
                        "outcome": "SKIPPED_SECRET_MISSING",
                    },
                ]
            )

        if openrouter_key:
            openrouter_url = os.environ.get(
                "OPENROUTER_CHAT_URL",
                "https://openrouter.ai/api/v1/chat/completions",
            )
            evidence["tests"].append(
                provider_call(
                    "openrouter",
                    openrouter_url,
                    openrouter_key,
                    args.openrouter_vision_model,
                    "sampled_frames",
                    images,
                )
            )
            evidence["tests"].append(
                provider_call(
                    "openrouter",
                    openrouter_url,
                    openrouter_key,
                    args.openrouter_audio_model,
                    "audio_excerpt",
                    audio_content,
                )
            )
        else:
            evidence["tests"].extend(
                [
                    {
                        "provider": "openrouter",
                        "modality": "sampled_frames",
                        "requested_model_id": args.openrouter_vision_model,
                        "outcome": "SKIPPED_SECRET_MISSING",
                    },
                    {
                        "provider": "openrouter",
                        "modality": "audio_excerpt",
                        "requested_model_id": args.openrouter_audio_model,
                        "outcome": "SKIPPED_SECRET_MISSING",
                    },
                ]
            )

    evidence["completed_at_utc"] = now()
    evidence["test_count"] = len(evidence["tests"])
    evidence["provider_success_count"] = sum(
        item.get("outcome")
        in {"HTTP_2XX_COMPLETION_PRESENT", "HTTP_2XX_TRANSCRIPTION_PRESENT"}
        for item in evidence["tests"]
    )
    evidence_path = args.output / "evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# JAMP Video Probe execution record",
        "",
        "Qualification: NOT_EVALUATED",
        "Scope: five sampled frames and audio excerpt 0–30s; not full-video understanding.",
        "",
        "| Test | Modality | Outcome | HTTP | Requested model | Actual model |",
        "|---|---|---|---:|---|---|",
    ]
    for item in evidence["tests"]:
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                item.get("test", item.get("provider", "unknown")),
                item.get("modality", "frames+audio"),
                item.get("outcome", "UNKNOWN"),
                item.get("http_status", "—"),
                item.get("requested_model_id", "—"),
                item.get("actual_model_id", "—"),
            )
        )
    (args.output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
