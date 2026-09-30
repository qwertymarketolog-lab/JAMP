#!/usr/bin/env python3
"""Controlled streaming replay for AnyModel cx/gpt-6-sol.

Uses the R1/R2/E01 semantic payload with stream=true and records
arrival timestamps for every requests.iter_content() chunk plus the
assembled raw response. This is read-only and does not touch Frozen Core.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import time
from typing import Any

import requests

CHAT_URL = "https://anymodel.org/v1/chat/completions"
MODEL = "cx/gpt-6-sol"
TIMEOUT_S = 60.0
DEFAULT_REPEATS = 3
OUTPUT = pathlib.Path("artifacts/research/r27_streaming_probe.json")

PAYLOAD = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "Reply with exactly: JAMP-E01-OK"}],
    "temperature": 0.0,
    "top_p": 1.0,
    "max_tokens": 256,
    "stream": True,
}


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def safe_headers(headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, str]:
    excluded = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
    return {str(k).lower(): str(v) for k, v in headers.items()
            if str(k).lower() not in excluded}


def run_once(api_key: str, index: int) -> dict[str, Any]:
    request_bytes = json.dumps(PAYLOAD, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request_sha = sha256(request_bytes)
    started_wall = now()
    started_mono = time.perf_counter()

    try:
        response = requests.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            data=request_bytes,
            stream=True,
            timeout=TIMEOUT_S,
        )
        headers = safe_headers(response.headers)
        chunks: list[bytes] = []
        events: list[dict[str, Any]] = []
        first_chunk_offset = None
        first_data_offset = None

        for chunk_index, chunk in enumerate(response.iter_content(chunk_size=None, decode_unicode=False)):
            if not chunk:
                continue
            offset = time.perf_counter() - started_mono
            chunks.append(chunk)
            if first_chunk_offset is None:
                first_chunk_offset = offset
            text = chunk.decode("utf-8", errors="replace")
            if first_data_offset is None and ("data:" in text or text.strip()):
                first_data_offset = offset
            events.append({
                "chunk_index": chunk_index,
                "offset_s": offset,
                "received_at": now(),
                "length_bytes": len(chunk),
                "sha256": sha256(chunk),
                "base64": base64.b64encode(chunk).decode("ascii"),
                "text": text,
            })

        elapsed_s = time.perf_counter() - started_mono
        raw = b"".join(chunks)
        response.close()
        return {
            "replay": index,
            "observed_at": started_wall,
            "request": PAYLOAD,
            "request_body_sha256": request_sha,
            "http": {
                "status_code": response.status_code,
                "headers": headers,
                "elapsed_s": elapsed_s,
            },
            "timing": {
                "first_chunk_s": first_chunk_offset,
                "first_data_s": first_data_offset,
                "last_chunk_s": events[-1]["offset_s"] if events else None,
                "chunk_count": len(events),
            },
            "response": {
                "raw_sha256": sha256(raw),
                "raw_length_bytes": len(raw),
                "chunks": events,
            },
        }
    except requests.RequestException as exc:
        elapsed_s = time.perf_counter() - started_mono
        return {
            "replay": index,
            "observed_at": started_wall,
            "request": PAYLOAD,
            "request_json_sha256": request_sha,
            "http": {
                "status_code": None,
                "headers": {},
                "elapsed_s": elapsed_s,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            "timing": {
                "first_chunk_s": None,
                "first_data_s": None,
                "last_chunk_s": None,
                "chunk_count": 0,
            },
            "response": None,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--output", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 10:
        raise SystemExit("--repeats must be 1..10")

    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        raise SystemExit("ANYMODEL_API_KEY is required")

    records = [run_once(api_key, i) for i in range(1, args.repeats + 1)]
    payload = {
        "probe_id": "anymodel-r27-streaming-v1",
        "created_at": now(),
        "chat_url": CHAT_URL,
        "model": MODEL,
        "timeout_s": TIMEOUT_S,
        "repeats": args.repeats,
        "payload": PAYLOAD,
        "request_body_sha256": sha256(
            json.dumps(PAYLOAD, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE {args.output}; repeats={len(records)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
