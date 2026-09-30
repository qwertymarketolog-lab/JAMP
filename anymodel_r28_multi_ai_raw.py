#!/usr/bin/env python3
"""R28 — fixed multi-model task with immutable raw outputs.

The harness does not score, edit, summarize, or judge model answers.
It records the exact request contract, HTTP metadata, and raw JSON response.
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
OUTPUT = pathlib.Path("artifacts/research/r28_multi_ai_raw.json")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "60"))

MODELS = [
    "am/diffusiongemma-26b-a4b-it",
    "am/gpt-oss-20b",
    "am/laguna-xs-2.1",
    "am/llama-3.2-11b-vision-instruct",
    "am/mistral-nemotron",
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

def main() -> int:
    key = os.environ.get("ANYMODEL_API_KEY")
    if not key:
        raise SystemExit("ANYMODEL_API_KEY is required")

    payloads = []
    for model in MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": TASK}],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 512,
            "stream": False,
        }
        request_bytes = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        started = time.perf_counter()
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
            elapsed = time.perf_counter() - started
            raw = response.content
            try:
                parsed: Any = response.json()
            except ValueError:
                parsed = None
            payloads.append({
                "model": model,
                "request": payload,
                "request_sha256": sha256_bytes(request_bytes),
                "observed_at": now(),
                "http": {
                    "status_code": response.status_code,
                    "headers": {
                        k.lower(): v for k, v in response.headers.items()
                        if k.lower() not in {"authorization", "set-cookie"}
                    },
                    "elapsed_s": elapsed,
                },
                "raw_response_sha256": sha256_bytes(raw),
                "raw_response_length_bytes": len(raw),
                "raw_response_text": raw.decode("utf-8", errors="replace"),
                "parsed_json": parsed,
            })
        except requests.RequestException as exc:
            payloads.append({
                "model": model,
                "request": payload,
                "request_sha256": sha256_bytes(request_bytes),
                "observed_at": now(),
                "http": {
                    "status_code": None,
                    "headers": {},
                    "elapsed_s": time.perf_counter() - started,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                "raw_response_sha256": None,
                "raw_response_length_bytes": 0,
                "raw_response_text": None,
                "parsed_json": None,
            })

    result = {
        "experiment_id": "R28",
        "schema_version": "r28-raw-v1",
        "created_at": now(),
        "chat_url": CHAT_URL,
        "task": TASK,
        "models": MODELS,
        "model_count": len(MODELS),
        "timeout_s": TIMEOUT_S,
        "records": payloads,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {OUTPUT}; records={len(payloads)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
# R28 trigger marker: execution-only commit; experiment contract unchanged.
