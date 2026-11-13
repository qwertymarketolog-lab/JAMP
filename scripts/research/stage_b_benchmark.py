#!/usr/bin/env python3
"""Controlled, sequential Stage B AnyModel benchmark. No retries; fail closed."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

from scripts.research.anymodel_deepseek_coefficient_probe import parse_coefficient

BASE_URL = os.getenv("ANYMODEL_BASE_URL", "https://anymodel.org")
CATALOG_URL = f"{BASE_URL}/v1/models"
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
OUT = pathlib.Path("artifacts/research/stage_b")
FROZEN_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"
MODELS = (
    "am/nemotron-3-ultra-550b-a55b",
    "ds/deepseek-v4-pro",
    "cx/gpt-6-astra",
)
MAX_OUTPUT_TOKENS = 2048
MAX_INPUT_TOKENS = 12000
NEMOTRON_DELAY_SECONDS = 60

TASKS = (
    {
        "id": "task1",
        "prompt": (
            "Дана последовательность a(n)=n² для целых n≥1. Докажи формально, "
            "что a(n+1)-a(n)=2n+1 для всех n≥1. Укажи метод и необходимые "
            "аксиомы. Проверка примеров доказательством не считается."
        ),
    },
    {
        "id": "task2",
        "prompt": (
            "Проведи аудит реального кода ниже. Найди минимальный воспроизводимый "
            "сценарий, при котором g1_verify.py может вернуть PASS при нарушении "
            "проверяемого условия. Укажи точные строки, причинную цепочку, "
            "тест-регрессию и минимальный безопасный фикс. Если дыры не найдены, "
            "обоснуй это по коду.\n\n"
            "=== scripts/g1_verify.py ===\n{g1_source}\n"
            "=== tests/test_g1_verify.py ===\n{test_source}"
        ),
    },
    {
        "id": "task5",
        "prompt": (
            "Предложи один проверяемый механизм снижения вероятности ошибок "
            "LLM при генерации кода без увеличения числа API-запросов. Опиши "
            "механизм, отличие от известных подходов, экспериментальную проверку "
            "и ограничения. Не заявляй эффективность без измерений."
        ),
    },
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, new_url: str) -> None:
        return None


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def valid_usage_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def request_once(method: str, url: str, api_key: str,
                 payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "JAMP-StageB/1.0",
        },
    )
    started = time.monotonic()
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=120) as response:
            raw = response.read()
            return {
                "http_status": response.status,
                "headers": dict(response.headers.items()),
                "raw_body": raw,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "transport_error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "http_status": exc.code,
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "raw_body": exc.read(),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "transport_error": None,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "http_status": None,
            "headers": {},
            "raw_body": b"",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "transport_error": f"{type(exc).__name__}: {exc}",
        }


def load_task2_prompt() -> str:
    paths = (pathlib.Path("scripts/g1_verify.py"), pathlib.Path("tests/test_g1_verify.py"))
    contents = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Required source file missing: {path}")
        contents.append(path.read_text(encoding="utf-8"))
    return TASKS[1]["prompt"].format(g1_source=contents[0], test_source=contents[1])


def catalog_models(raw: bytes) -> list[dict[str, Any]]:
    data = json.loads(raw.decode("utf-8"))
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Catalog data must be a list")
    return rows


def preflight(catalog: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    normalized: dict[str, tuple[float, float]] = {}
    for model_id in MODELS:
        matches = [row for row in catalog if isinstance(row, dict) and row.get("id") == model_id]
        if len(matches) != 1:
            raise ValueError(f"{model_id}: expected one exact catalog match, got {len(matches)}")
        billing = matches[0].get("billing")
        coefficients = parse_coefficient(billing) if isinstance(billing, dict) else None
        if coefficients is None:
            raise ValueError(f"{model_id}: missing or invalid coefficient")
        normalized[model_id] = coefficients
    return normalized


def worst_case_budget(coefficients: dict[str, tuple[float, float]]) -> float:
    per_model = {
        model: MAX_INPUT_TOKENS * pair[0] + MAX_OUTPUT_TOKENS * pair[1]
        for model, pair in coefficients.items()
    }
    return sum(per_model.values()) * len(TASKS)


def save_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def run(balance_before: int, budget_cap: float) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if any(OUT.iterdir()):
        raise SystemExit(f"Evidence directory is not empty: {OUT}")
    frozen = subprocess.check_output(
        ["git", "rev-parse", "HEAD:src/jamp/run.py"], text=True
    ).strip()
    if frozen != FROZEN_BLOB:
        raise SystemExit("Frozen Core mismatch; no API calls made")
    api_key = os.getenv("ANYMODEL_API_KEY")
    if not api_key:
        raise SystemExit("ANYMODEL_API_KEY missing; no API calls made")
    task2 = load_task2_prompt()

    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment": "JAMP_STAGE_B_3X3",
        "status": "PREFLIGHT",
        "created_at": utc_now(),
        "github": {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "sha": os.getenv("GITHUB_SHA"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        },
        "frozen_core": {"expected_blob": FROZEN_BLOB, "observed_blob": frozen,
                        "delta_zero": True},
        "balance_before_units": balance_before,
        "budget_cap_units": budget_cap,
        "models": list(MODELS),
        "tasks": [task["id"] for task in TASKS],
        "planned_requests": 9,
        "completed_requests": 0,
        "retry_count": 0,
        "redirects_followed": 0,
        "results": [],
    }
    catalog_result = request_once("GET", CATALOG_URL, api_key)
    catalog_raw = catalog_result["raw_body"]
    (OUT / "catalog_raw.json").write_bytes(catalog_raw)
    manifest["catalog"] = {
        "http_status": catalog_result["http_status"],
        "headers": catalog_result["headers"],
        "sha256": digest(catalog_raw),
        "latency_ms": catalog_result["latency_ms"],
    }
    if catalog_result["transport_error"] or catalog_result["http_status"] != 200:
        manifest.update(status="BLOCKED", stop_reason="Catalog GET failed")
        save_json(OUT / "run_manifest.json", manifest)
        return 0
    try:
        coefficients = preflight(catalog_models(catalog_raw))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        manifest.update(status="BLOCKED", stop_reason=f"Catalog preflight failed: {exc}")
        save_json(OUT / "run_manifest.json", manifest)
        return 0
    manifest["coefficients"] = {
        model: {"input": pair[0], "output": pair[1]}
        for model, pair in coefficients.items()
    }
    manifest["worst_case_budget_units"] = worst_case_budget(coefficients)
    if manifest["worst_case_budget_units"] > budget_cap:
        manifest.update(status="BLOCKED", stop_reason="Worst-case budget exceeds operator cap")
        save_json(OUT / "run_manifest.json", manifest)
        return 0

    manifest["status"] = "RUNNING"
    prompts = [TASKS[0]["prompt"], task2, TASKS[2]["prompt"]]
    stop_reason = None
    for model_index, model_id in enumerate(MODELS):
        for task_index, task in enumerate(TASKS):
            if model_id == MODELS[0] and task_index > 0:
                time.sleep(NEMOTRON_DELAY_SECONDS)
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": prompts[task_index]}],
                "max_tokens": MAX_OUTPUT_TOKENS,
                "temperature": 0,
            }
            response = request_once("POST", CHAT_URL, api_key, payload)
            raw = response["raw_body"]
            response_name = f"{model_index + 1}_{task['id']}_response.json"
            (OUT / response_name).write_bytes(raw)
            record: dict[str, Any] = {
                "sequence": len(manifest["results"]) + 1,
                "model_id": model_id,
                "task_id": task["id"],
                "requested_at": utc_now(),
                "http_status": response["http_status"],
                "headers": response["headers"],
                "latency_ms": response["latency_ms"],
                "transport_error": response["transport_error"],
                "raw_response_file": response_name,
                "raw_response_sha256": digest(raw),
                "status": "FAILED",
            }
            if response["transport_error"] or response["http_status"] != 200:
                record["failure"] = "HTTP or transport failure; series stopped"
                manifest["results"].append(record)
                stop_reason = record["failure"]
                break
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                record["failure"] = "Invalid JSON response; series stopped"
                manifest["results"].append(record)
                stop_reason = record["failure"]
                break
            usage = body.get("usage") if isinstance(body, dict) else None
            usage = usage if isinstance(usage, dict) else {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            if not all(valid_usage_int(v) for v in
                       (prompt_tokens, completion_tokens, total_tokens)):
                record["failure"] = "Missing or invalid token usage; series stopped"
                manifest["results"].append(record)
                stop_reason = record["failure"]
                break
            if prompt_tokens + completion_tokens != total_tokens:
                record["failure"] = "Inconsistent token usage; series stopped"
                manifest["results"].append(record)
                stop_reason = record["failure"]
                break
            in_coeff, out_coeff = coefficients[model_id]
            record.update(
                status="SUCCESS",
                response_id=body.get("id"),
                response_model=body.get("model"),
                usage={"prompt_tokens": prompt_tokens,
                       "completion_tokens": completion_tokens,
                       "total_tokens": total_tokens},
                expected_balance_debit_units=(
                    prompt_tokens * in_coeff + completion_tokens * out_coeff
                ),
                assistant_content=(
                    body.get("choices", [{}])[0].get("message", {}).get("content")
                    if isinstance(body.get("choices"), list) and body["choices"]
                    else None
                ),
            )
            manifest["results"].append(record)
            manifest["completed_requests"] += 1
        if stop_reason:
            break
    manifest.update(
        status="COMPLETED" if manifest["completed_requests"] == 9 else "STOPPED",
        stop_reason=stop_reason,
        finished_at=utc_now(),
        calculated_total_debit_units=sum(
            row.get("expected_balance_debit_units", 0) for row in manifest["results"]
        ),
        balance_after_units=None,
        balance_reconciliation="MANUAL_REQUIRED",
        model_qualification="NOT_STARTED",
        routing_eligibility="REFUSE",
    )
    save_json(OUT / "run_manifest.json", manifest)
    checksums = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            checksums.append(f"{digest(path.read_bytes())}  {path.name}")
    (OUT / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--balance-before-units", type=int, required=True)
    parser.add_argument("--budget-cap-units", type=float, required=True)
    args = parser.parse_args()
    if args.balance_before_units <= 0 or not math.isfinite(args.budget_cap_units) or args.budget_cap_units <= 0:
        parser.error("balance and budget cap must be positive finite values")
    return run(args.balance_before_units, args.budget_cap_units)


if __name__ == "__main__":
    raise SystemExit(main())
