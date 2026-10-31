#!/usr/bin/env python3
"""R30 — quantify replay variance for fixed AnyModel request contracts.

The harness preserves raw HTTP responses and metadata. It does not score,
edit, normalize, or repair model output.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import time
from typing import Any

import requests

CHAT_URL = os.environ.get("ANYMODEL_CHAT_URL", "https://anymodel.org/v1/chat/completions")
OUTPUT = pathlib.Path("artifacts/research/r30_replay_variance.json")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "120"))
REPLAYS = 5

MODELS = [
    "am/laguna-xs-2.1",
    "am/gpt-oss-20b",
]

TASK = """Research task:
Explain what the International Astronomical Union decided about Pluto in August 2006.
Return exactly three numbered points:
1) the formal classification adopted;
2) the three criteria used in the adopted definition of a planet;
3) the immediate consequence for Pluto.
Do not discuss later changes or opinions. If uncertain, state the uncertainty explicitly."""


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_payload(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": TASK}],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 512,
        "stream": False,
    }


def extract_content(parsed: Any) -> str | None:
    if not isinstance(parsed, dict):
        return None
    choices = parsed.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


def extract_reasoning_tokens(usage: Any) -> int | None:
    if not isinstance(usage, dict):
        return None
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict):
        value = details.get("reasoning_tokens")
        if isinstance(value, int):
            return value
    value = usage.get("reasoning_tokens")
    return value if isinstance(value, int) else None


def provenance_headers(headers: dict[str, str]) -> dict[str, str | None]:
    return {
        "cf_ray": headers.get("cf-ray"),
        "cf_cache_status": headers.get("cf-cache-status"),
        "provider_edge": headers.get("provider-edge"),
    }


def main() -> int:
    key = os.environ.get("ANYMODEL_API_KEY")
    if not key:
        raise SystemExit("ANYMODEL_API_KEY is required")

    results: dict[str, list[dict[str, Any]]] = {}

    for model in MODELS:
        payload = build_payload(model)
        request_bytes = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        request_hash = sha256_bytes(request_bytes)
        first_content: str | None = None
        model_results: list[dict[str, Any]] = []

        for replay_index in range(1, REPLAYS + 1):
            started = time.perf_counter()
            record: dict[str, Any] = {
                "replay_index": replay_index,
                "observed_at": now(),
                "request": payload,
                "request_sha256": request_hash,
            }

            try:
                response = requests.post(
                    CHAT_URL,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    data=request_bytes,
                    timeout=TIMEOUT_S,
                )
                elapsed_s = time.perf_counter() - started
                raw = response.content
                try:
                    parsed: Any = response.json()
                except ValueError:
                    parsed = None

                headers = {
                    k.lower(): v
                    for k, v in response.headers.items()
                    if k.lower() not in {"authorization", "set-cookie"}
                }
                content = extract_content(parsed)
                usage = parsed.get("usage") if isinstance(parsed, dict) else None

                if replay_index == 1:
                    first_content = content

                record.update(
                    {
                        "http_status": response.status_code,
                        "latency_ms": elapsed_s * 1000.0,
                        "ttfb_ms": None,
                        "response_hash": sha256_bytes(raw),
                        "raw_response_length_bytes": len(raw),
                        "raw_response_text": raw.decode(
                            "utf-8", errors="replace"
                        ),
                        "parsed_json": parsed,
                        "content": content,
                        "exact_match_with_first": (
                            replay_index == 1
                            or (
                                content is not None
                                and first_content is not None
                                and content == first_content
                            )
                        ),
                        "usage": usage,
                        "prompt_tokens": (
                            usage.get("prompt_tokens")
                            if isinstance(usage, dict)
                            else None
                        ),
                        "completion_tokens": (
                            usage.get("completion_tokens")
                            if isinstance(usage, dict)
                            else None
                        ),
                        "reasoning_tokens": extract_reasoning_tokens(usage),
                        "headers": headers,
                        "header_provenance": provenance_headers(headers),
                    }
                )
            except requests.RequestException as exc:
                record.update(
                    {
                        "http_status": None,
                        "latency_ms": (time.perf_counter() - started) * 1000.0,
                        "ttfb_ms": None,
                        "response_hash": None,
                        "raw_response_length_bytes": 0,
                        "raw_response_text": None,
                        "parsed_json": None,
                        "content": None,
                        "exact_match_with_first": False,
                        "usage": None,
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "reasoning_tokens": None,
                        "headers": {},
                        "header_provenance": {
                            "cf_ray": None,
                            "cf_cache_status": None,
                            "provider_edge": None,
                        },
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

            if record["request_sha256"] != request_hash:
                raise RuntimeError("request hash invariant violated")

            model_results.append(record)

        results[model] = model_results

    result = {
        "experiment_id": "R30",
        "protocol_version": "1.0",
        "created_at": now(),
        "chat_url": CHAT_URL,
        "target_models": MODELS,
        "replays_per_model": REPLAYS,
        "timeout_s": TIMEOUT_S,
        "request_contract": {
            "prompt": TASK,
            "parameters": {
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 512,
                "stream": False,
            },
            "request_hashes": {
                model: results[model][0]["request_sha256"] for model in MODELS
            },
        },
        "results": results,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"WROTE {OUTPUT}; models={len(MODELS)}; "
        f"total_replays={len(MODELS) * REPLAYS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
