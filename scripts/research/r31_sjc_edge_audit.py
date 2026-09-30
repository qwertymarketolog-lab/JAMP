#!/usr/bin/env python3
"""R31 — observe Laguna edge routing and generation throughput.

Fixed request contract; sequential replays; preserves raw response metadata.
The harness does not attempt to force a Cloudflare edge location.
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
MODEL = "am/laguna-xs-2.1"
OUTPUT = pathlib.Path("artifacts/research/r31_sjc_edge_audit.json")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "120"))
REPEATS = 15

PROMPT = """Research task:
Explain what the International Astronomical Union decided about Pluto in August 2006.
Return exactly three numbered points:
1) the formal classification adopted;
2) the three criteria used in the adopted definition of a planet;
3) the immediate consequence for Pluto.
Do not discuss later changes or opinions. If uncertain, state the uncertainty explicitly."""

PAYLOAD = {
    "model": MODEL,
    "messages": [{"role": "user", "content": PROMPT}],
    "temperature": 0.0,
    "top_p": 1.0,
    "max_tokens": 512,
    "stream": False,
}


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def safe_headers(headers: requests.structures.CaseInsensitiveDict[str]) -> dict[str, str]:
    excluded = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
    return {
        str(k).lower(): str(v)
        for k, v in headers.items()
        if str(k).lower() not in excluded
    }


def run_once(api_key: str, index: int) -> dict[str, Any]:
    request_bytes = json.dumps(
        PAYLOAD, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    request_hash = sha256(request_bytes)
    started_at = now()
    started = time.perf_counter()

    try:
        response = requests.post(
            CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            data=request_bytes,
            timeout=TIMEOUT_S,
        )
        elapsed = time.perf_counter() - started
        raw = response.content
        headers = safe_headers(response.headers)

        parsed = None
        parse_error = None
        try:
            parsed = response.json()
        except ValueError as exc:
            parse_error = str(exc)

        record: dict[str, Any] = {
            "replay": index,
            "observed_at": started_at,
            "request_sha256": request_hash,
            "http": {
                "status_code": response.status_code,
                "elapsed_s": elapsed,
                "headers": headers,
            },
            "raw_response_sha256": sha256(raw),
            "raw_response_length_bytes": len(raw),
            "raw_response_text": raw.decode("utf-8", errors="replace"),
            "parsed_json": parsed,
            "parse_error": parse_error,
        }

        nvext = None
        if isinstance(parsed, dict):
            nvext = parsed.get("nvext")
            if nvext is None:
                choices = parsed.get("choices")
                if isinstance(choices, list) and choices:
                    message = choices[0].get("message", {})
                    if isinstance(message, dict):
                        nvext = message.get("nvext")
        record["nvext"] = nvext
        return record

    except requests.RequestException as exc:
        return {
            "replay": index,
            "observed_at": started_at,
            "request_sha256": request_hash,
            "http": {
                "status_code": None,
                "elapsed_s": time.perf_counter() - started,
                "headers": {},
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            "raw_response_sha256": None,
            "raw_response_length_bytes": 0,
            "raw_response_text": None,
            "parsed_json": None,
            "parse_error": None,
            "nvext": None,
        }


def main() -> int:
    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        raise SystemExit("ANYMODEL_API_KEY is required")

    request_bytes = json.dumps(
        PAYLOAD, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    request_hash = sha256(request_bytes)
    records = [run_once(api_key, i) for i in range(1, REPEATS + 1)]

    payload = {
        "experiment_id": "R31",
        "purpose": "Observe Laguna CF-Ray edge routing and generation throughput",
        "created_at": now(),
        "chat_url": CHAT_URL,
        "model": MODEL,
        "timeout_s": TIMEOUT_S,
        "repeats": REPEATS,
        "request_sha256": request_hash,
        "payload": PAYLOAD,
        "routing_control": "OBSERVATIONAL_ONLY; edge location is not client-forced",
        "records": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {OUTPUT}; repeats={len(records)}; request_sha256={request_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
