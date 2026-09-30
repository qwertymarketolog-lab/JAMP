#!/usr/bin/env python3
"""R32 — balanced round-robin multi-model latency/variance matrix.

Runs L1 -> G1 -> S1 ... L15 -> G15 -> S15 with one fixed request
contract per model. Routing is observational only; no edge is forced.
Raw HTTP, headers, response body, and nvext are retained.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import time
from typing import Any

import httpx

CHAT_URL = os.environ.get("ANYMODEL_CHAT_URL", "https://anymodel.org/v1/chat/completions")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "120"))
REPLAYS_PER_MODEL = 15
OUTPUT = pathlib.Path("artifacts/research/r32_round_robin_matrix.json")

MODELS = [
    "am/laguna-xs-2.1",
    "am/gpt-oss-20b",
    "cx/gpt-6-sol",
]

PROMPT = """Research task:
Explain what the International Astronomical Union decided about Pluto in August 2006.
Return exactly three numbered points:
1) the formal classification adopted;
2) the three criteria used in the adopted definition of a planet;
3) the immediate consequence for Pluto.
Do not discuss later changes or opinions. If uncertain, state the uncertainty explicitly."""


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def payload_for(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 512,
        "stream": False,
    }


def request_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256(raw)


def safe_headers(headers: httpx.Headers) -> dict[str, str]:
    excluded = {"authorization", "proxy-authorization", "cookie", "set-cookie"}
    return {
        str(k).lower(): str(v)
        for k, v in headers.items()
        if str(k).lower() not in excluded
    }


def nested_number(obj: Any, names: tuple[str, ...]) -> float | None:
    if isinstance(obj, dict):
        for name in names:
            value = obj.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        for value in obj.values():
            found = nested_number(value, names)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = nested_number(value, names)
            if found is not None:
                return found
    return None


def extract_nvext(parsed: Any) -> Any:
    if not isinstance(parsed, dict):
        return None
    if "nvext" in parsed:
        return parsed["nvext"]
    choices = parsed.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message")
        if isinstance(message, dict) and "nvext" in message:
            return message["nvext"]
    return None


def normalize_nvext(nvext: Any) -> dict[str, Any]:
    if nvext is None:
        return {
            "e2e_latency_sec": None,
            "generation_tps": None,
            "draft_tokens_per_second": None,
            "scheduler": None,
        }
    return {
        "e2e_latency_sec": nested_number(
            nvext,
            ("e2e_latency_sec", "e2e_latency_s", "e2e_seconds", "e2e"),
        ),
        "generation_tps": nested_number(
            nvext,
            ("generation_tps", "gen_tps", "tokens_per_second"),
        ),
        "draft_tokens_per_second": nested_number(
            nvext,
            ("draft_tokens_per_second", "draft_tps"),
        ),
        "scheduler": (
            nvext.get("scheduler")
            if isinstance(nvext, dict)
            else None
        ),
    }


def classify_2d(t_gen: float | None, t_overhead: float) -> str:
    # Fail closed: missing backend timing is never converted into a fabricated
    # generation value. A >100 s wall stall without backend timing is transport.
    if t_overhead > 100.0 and t_gen is None:
        return "TRANSPORT_STALL"
    if t_gen is not None and t_overhead > 100.0 and t_gen <= 6.0:
        return "TRANSPORT_STALL"
    if t_gen is not None and t_gen > 5.0 and t_overhead <= 3.0:
        return "GENERATION_THROTTLED"
    if t_gen is not None and t_gen <= 5.0 and t_overhead <= 3.0:
        return "NOMINAL_BASELINE"
    return "DUAL_AXIS_DEGRADED"


def run_once(client: httpx.Client, api_key: str, model: str, cycle: int) -> dict[str, Any]:
    payload = payload_for(model)
    request_sha = request_hash(payload)
    started_at = now()
    started = time.perf_counter()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = client.post(CHAT_URL, headers=headers, json=payload)
        wall = time.perf_counter() - started
        raw = response.content
        response_headers = safe_headers(response.headers)

        parsed = None
        parse_error = None
        try:
            parsed = response.json()
        except ValueError as exc:
            parse_error = str(exc)

        nvext = extract_nvext(parsed)
        normalized = normalize_nvext(nvext)
        t_gen = normalized["e2e_latency_sec"]
        t_overhead = max(0.0, wall - t_gen) if t_gen is not None else wall

        return {
            "trace_id": f"R32-{cycle:02d}-{model.split('/')[-1]}",
            "cycle": cycle,
            "model": model,
            "request_sha256": request_sha,
            "observed_at": started_at,
            "http": {
                "status_code": response.status_code,
                "wall_elapsed_s": wall,
                "headers": response_headers,
            },
            "metrics": {
                "t_wall_sec": wall,
                "t_gen_sec": t_gen,
                "t_overhead_sec": t_overhead,
                "generation_tps": normalized["generation_tps"],
                "draft_tokens_per_second": normalized["draft_tokens_per_second"],
                "scheduler": normalized["scheduler"],
            },
            "classification": classify_2d(t_gen, t_overhead),
            "root_cause": "UNKNOWN",
            "raw_response_sha256": sha256(raw),
            "raw_response_length_bytes": len(raw),
            "raw_response_text": raw.decode("utf-8", errors="replace"),
            "parsed_json": parsed,
            "parse_error": parse_error,
            "nvext": nvext,
        }
    except httpx.HTTPError as exc:
        wall = time.perf_counter() - started
        return {
            "trace_id": f"R32-{cycle:02d}-{model.split('/')[-1]}",
            "cycle": cycle,
            "model": model,
            "request_sha256": request_sha,
            "observed_at": started_at,
            "http": {
                "status_code": None,
                "wall_elapsed_s": wall,
                "headers": {},
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            "metrics": {
                "t_wall_sec": wall,
                "t_gen_sec": None,
                "t_overhead_sec": wall,
                "generation_tps": None,
                "draft_tokens_per_second": None,
                "scheduler": None,
            },
            "classification": classify_2d(None, wall),
            "root_cause": "UNKNOWN",
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

    request_hashes = {model: request_hash(payload_for(model)) for model in MODELS}
    records: list[dict[str, Any]] = []

    timeout = httpx.Timeout(TIMEOUT_S)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for cycle in range(1, REPLAYS_PER_MODEL + 1):
            for model in MODELS:
                records.append(run_once(client, api_key, model, cycle))

    payload = {
        "experiment_id": "R32",
        "purpose": "Balanced round-robin multi-model variance under one fixed workload",
        "created_at": now(),
        "chat_url": CHAT_URL,
        "models": MODELS,
        "replays_per_model": REPLAYS_PER_MODEL,
        "total_transactions": len(records),
        "ordering": "L1,G1,S1 ... L15,G15,S15",
        "routing_control": "OBSERVATIONAL_ONLY; edge location is not client-forced",
        "request_contract": {
            "prompt": PROMPT,
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 512,
            "stream": False,
            "request_sha256_by_model": request_hashes,
        },
        "taxonomy": "R31_2D_CONTRACT",
        "records": records,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"WROTE {OUTPUT}; transactions={len(records)}; "
        f"request_hashes={json.dumps(request_hashes, sort_keys=True)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
