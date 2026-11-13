#!/usr/bin/env python3
"""Controlled, sequential Stage B AnyModel benchmark. No retries; fail closed."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import math
import os
import pathlib
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any


def parse_coefficient(billing: dict[str, Any]) -> tuple[float, float] | None:
    """Normalize catalog coefficients; reject booleans, negatives and non-finite values."""
    coefficient = billing.get("coefficient")

    def valid_number(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )

    if valid_number(coefficient):
        value = float(coefficient)
        return value, value
    if isinstance(coefficient, dict):
        input_value = coefficient.get("input")
        output_value = coefficient.get("output")
        if valid_number(input_value) and valid_number(output_value):
            return float(input_value), float(output_value)
    return None

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
INPUT_TOKEN_SAFETY_MARGIN = 1024
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
    response = None
    try:
        response = opener.open(req, timeout=120)
        with response:
            raw = response.read()
            return {
                "http_status": response.status,
                "headers": dict(response.headers.items()),
                "raw_body": raw,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "transport_error": None,
                "transport_status": "COMPLETE",
            }
    except urllib.error.HTTPError as exc:
        return {
            "http_status": exc.code,
            "headers": dict(exc.headers.items()) if exc.headers else {},
            "raw_body": exc.read(),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "transport_error": None,
            "transport_status": "HTTP_ERROR",
        }
    except http.client.IncompleteRead as exc:
        return {
            "http_status": getattr(response, "status", None),
            "headers": dict(response.headers.items()) if response is not None else {},
            "raw_body": exc.partial or b"",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "transport_error": f"IncompleteRead: {exc}",
            "transport_status": "INCOMPLETE_READ",
            "billing_status": "UNKNOWN",
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "http_status": getattr(response, "status", None),
            "headers": dict(response.headers.items()) if response is not None else {},
            "raw_body": b"",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "transport_error": f"{type(exc).__name__}: {exc}",
            "transport_status": "TRANSPORT_ERROR",
            "billing_status": "UNKNOWN",
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


def worst_case_budget(
    coefficients: dict[str, tuple[float, float]], prompts: list[str]
) -> float:
    # UTF-8 byte length is a conservative tokenizer-independent input bound;
    # add margin for chat framing/provider-added tokens.
    input_bounds = [len(prompt.encode("utf-8")) + INPUT_TOKEN_SAFETY_MARGIN
                    for prompt in prompts]
    return sum(
        input_bounds[index] * pair[0] + MAX_OUTPUT_TOKENS * pair[1]
        for pair in coefficients.values()
        for index in range(len(prompts))
    )


def save_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")




RESUME_SOURCE_RUN_ID = "43381268827"
RESUME_SOURCE_SHA = "41f4cbe4facaafaecec088cc7260bd76605984e6"
RESUME_EXPECTED_SUCCESS = {
    ("am/nemotron-3-ultra-550b-a55b", "task1"),
    ("am/nemotron-3-ultra-550b-a55b", "task2"),
    ("am/nemotron-3-ultra-550b-a55b", "task5"),
    ("ds/deepseek-v4-pro", "task1"),
    ("ds/deepseek-v4-pro", "task2"),
    ("ds/deepseek-v4-pro", "task5"),
    ("cx/gpt-6-astra", "task1"),
}


def load_resume_evidence(source_dir: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    """Load only the pinned Stage B artifact and verify every SUCCESS byte-for-byte."""
    manifest_path = source_dir / "run_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Resume manifest missing")
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    github = source.get("github", {})
    if github.get("run_id") != RESUME_SOURCE_RUN_ID or github.get("sha") != RESUME_SOURCE_SHA:
        raise ValueError("Resume source run/SHA mismatch")
    if source.get("status") != "RUNNING" or source.get("completed_requests") != 7:
        raise ValueError("Resume source is not the expected seven-result partial run")
    if source.get("catalog", {}).get("http_status") != 200:
        raise ValueError("Resume source catalog was not HTTP 200")
    frozen = source.get("frozen_core", {})
    if frozen.get("delta_zero") is not True or frozen.get("observed_blob") != FROZEN_BLOB:
        raise ValueError("Resume source Frozen Core evidence mismatch")
    rows = source.get("results")
    if not isinstance(rows, list):
        raise ValueError("Resume results must be a list")
    successes = [row for row in rows if isinstance(row, dict) and row.get("status") == "SUCCESS"]
    identities = [(row.get("model_id"), row.get("task_id")) for row in successes]
    if len(successes) != 7 or len(set(identities)) != 7 or set(identities) != RESUME_EXPECTED_SUCCESS:
        raise ValueError("Resume source SUCCESS inventory mismatch")
    for row in successes:
        name = row.get("raw_response_file")
        expected = row.get("raw_response_sha256")
        if not isinstance(name, str) or pathlib.Path(name).name != name:
            raise ValueError("Unsafe raw response filename in resume manifest")
        raw_path = source_dir / name
        if not raw_path.is_file() or not isinstance(expected, str) or digest(raw_path.read_bytes()) != expected:
            raise ValueError(f"INTEGRITY_MISMATCH: {name}")
    catalog_path = source_dir / "catalog_raw.json"
    if not catalog_path.is_file() or digest(catalog_path.read_bytes()) != source.get("catalog", {}).get("sha256"):
        raise ValueError("INTEGRITY_MISMATCH: catalog_raw.json")
    return source, successes, catalog_path.read_bytes()


def run(balance_before: int, budget_cap: float, resume_from: pathlib.Path,
        retry_astra_task2: bool, balance_before_usd: float | None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if any(OUT.iterdir()):
        raise SystemExit(f"Evidence directory is not empty: {OUT}")
    source, prior_successes, catalog_raw = load_resume_evidence(resume_from)
    frozen = subprocess.check_output(["git", "rev-parse", "HEAD:src/jamp/run.py"], text=True).strip()
    if frozen != FROZEN_BLOB:
        raise SystemExit("Frozen Core mismatch; no API calls made")
    for row in prior_successes:
        shutil.copy2(resume_from / row["raw_response_file"], OUT / row["raw_response_file"])
    shutil.copy2(resume_from / "catalog_raw.json", OUT / "catalog_raw.json")

    api_key = os.getenv("ANYMODEL_API_KEY")
    if not api_key:
        raise SystemExit("ANYMODEL_API_KEY missing; no API calls made")
    task2_prompt = load_task2_prompt()
    prompt_by_id = {"task1": TASKS[0]["prompt"], "task2": task2_prompt, "task5": TASKS[2]["prompt"]}
    coefficients = preflight(catalog_models(catalog_raw))
    results = [dict(row) for row in prior_successes]
    incomplete = {
        "sequence": 8,
        "model_id": "cx/gpt-6-astra",
        "task_id": "task2",
        "requested_at": None,
        "status": "INCOMPLETE_READ",
        "transport_error": "IncompleteRead(291 bytes read); chunked response terminated",
        "raw_response_file": None,
        "raw_response_sha256": None,
        "partial_data_bytes": 291,
        "billing_status": "UNKNOWN",
        "billing_charged": None,
        "source_run_id": RESUME_SOURCE_RUN_ID,
        "automatic_retry": False,
    }
    results.append(incomplete)
    success_pairs = {(row["model_id"], row["task_id"]) for row in prior_successes}
    pending = []
    if retry_astra_task2:
        pending.append(("cx/gpt-6-astra", "task2"))
    pending.append(("cx/gpt-6-astra", "task5"))
    pending = [(model, task_id) for model, task_id in pending if (model, task_id) not in success_pairs]
    pending_coefficients = {model: coefficients[model] for model, _ in pending}
    pending_prompts = [prompt_by_id[task_id] for _, task_id in pending]
    worst_case = worst_case_budget(pending_coefficients, pending_prompts) if pending else 0.0
    if worst_case > budget_cap:
        raise SystemExit(f"BLOCKED: remaining-task worst-case {worst_case} exceeds cap {budget_cap}")

    manifest: dict[str, Any] = {
        "schema_version": "1.1",
        "experiment": "JAMP_STAGE_B_3X3",
        "status": "RUNNING",
        "created_at": utc_now(),
        "github": {
            "repository": os.getenv("GITHUB_REPOSITORY"),
            "sha": os.getenv("GITHUB_SHA"),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        },
        "frozen_core": {"expected_blob": FROZEN_BLOB, "observed_blob": frozen, "delta_zero": frozen == FROZEN_BLOB},
        "resume_source": {
            "run_id": RESUME_SOURCE_RUN_ID,
            "sha": RESUME_SOURCE_SHA,
            "completed_successes_imported": len(prior_successes),
            "integrity_verified": True,
        },
        "balance_before_usd": balance_before_usd,
        "balance_before_tokens": balance_before,
        "balance_after_tokens": None,
        "astra_task2_billing_status": "UNKNOWN",
        "astra_task2_charged": None,
        "budget_cap_units": budget_cap,
        "models": list(MODELS),
        "tasks": [task["id"] for task in TASKS],
        "planned_requests": 9,
        "completed_requests": 7,
        "attempted_requests_this_run": 0,
        "retry_count": 0,
        "redirects_followed": 0,
        "worst_case_budget_units": worst_case,
        "results": results,
        "status_note": f"Astra task2 original attempt remains INCOMPLETE_READ/UNKNOWN; retry explicitly authorized={retry_astra_task2}.",
        "model_qualification": "NOT_STARTED",
        "routing_eligibility": "REFUSE",
    }
    save_json(OUT / "run_manifest.json", manifest)
    stop_reason = None
    for model_id, task_id in pending:
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt_by_id[task_id]}],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0,
        }
        response = request_once("POST", CHAT_URL, api_key, payload)
        raw = response["raw_body"]
        model_index = MODELS.index(model_id) + 1
        response_name = f"{model_index}_{task_id}_response.json"
        (OUT / response_name).write_bytes(raw)
        sequence = len(manifest["results"]) + 1
        record: dict[str, Any] = {
            "sequence": sequence,
            "model_id": model_id,
            "task_id": task_id,
            "requested_at": utc_now(),
            "http_status": response["http_status"],
            "headers": response["headers"],
            "latency_ms": response["latency_ms"],
            "transport_error": response["transport_error"],
            "raw_response_file": response_name,
            "raw_response_sha256": digest(raw),
            "status": "FAILED",
        }
        manifest["attempted_requests_this_run"] += 1
        if response.get("transport_status") == "INCOMPLETE_READ":
            record.update(status="INCOMPLETE_READ", billing_status="UNKNOWN",
                          billing_charged=None, partial_data_bytes=len(raw))
            stop_reason = "IncompleteRead; billing unknown; fail closed"
        elif response["transport_error"] or response["http_status"] != 200:
            record.update(billing_status="UNKNOWN", billing_charged=None,
                          failure="HTTP or transport failure")
            stop_reason = record["failure"]
        else:
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                record.update(billing_status="UNKNOWN", billing_charged=None,
                              failure="Invalid JSON response")
                stop_reason = record["failure"]
            else:
                usage = body.get("usage") if isinstance(body, dict) else None
                usage = usage if isinstance(usage, dict) else {}
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")
                if not all(valid_usage_int(value) for value in (prompt_tokens, completion_tokens, total_tokens)) or prompt_tokens + completion_tokens != total_tokens:
                    record.update(billing_status="UNKNOWN", billing_charged=None,
                                  failure="Missing or inconsistent token usage")
                    stop_reason = record["failure"]
                else:
                    in_coeff, out_coeff = coefficients[model_id]
                    choices = body.get("choices")
                    message = choices[0].get("message", {}) if isinstance(choices, list) and choices else {}
                    record.update(
                        status="SUCCESS",
                        response_id=body.get("id"),
                        response_model=body.get("model"),
                        usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
                        expected_balance_debit_units=prompt_tokens * in_coeff + completion_tokens * out_coeff,
                        assistant_content=message.get("content"),
                        billing_status="USAGE_REPORTED",
                    )
                    manifest["completed_requests"] += 1
        manifest["results"].append(record)
        save_json(OUT / "run_manifest.json", manifest)
        if stop_reason:
            break
    manifest.update(
        status="PARTIAL_COMPLETED" if any(row.get("model_id") == "cx/gpt-6-astra" and row.get("task_id") == "task5" and row.get("status") == "SUCCESS" for row in manifest["results"]) else "STOPPED",
        stop_reason=stop_reason,
        finished_at=utc_now(),
        calculated_total_debit_units=sum(row.get("expected_balance_debit_units", 0) for row in manifest["results"]),
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
    return 0 if manifest["status"] == "PARTIAL_COMPLETED" else 1

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--balance-before-units", type=int, required=True)
    parser.add_argument("--budget-cap-units", type=float, required=True)
    parser.add_argument("--balance-before-usd", type=float, default=None)
    parser.add_argument("--resume-from", type=pathlib.Path, required=True)
    parser.add_argument("--retry-astra-task2", action="store_true", default=False)
    args = parser.parse_args()
    if (
        args.balance_before_units <= 0
        or not math.isfinite(args.budget_cap_units)
        or args.budget_cap_units <= 0
        or (args.balance_before_usd is not None and (not math.isfinite(args.balance_before_usd) or args.balance_before_usd < 0))
    ):
        parser.error("balance and budget cap must be positive finite values")
    return run(args.balance_before_units, args.budget_cap_units, args.resume_from,
               args.retry_astra_task2, args.balance_before_usd)


if __name__ == "__main__":
    raise SystemExit(main())
