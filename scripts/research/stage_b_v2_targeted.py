#!/usr/bin/env python3
"""Stage B v2 targeted experiment. Dry-run by default; no retries or fallbacks."""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import http.client
import json
import math
import os
import pathlib
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any

BASE_URL = os.getenv("ANYMODEL_BASE_URL", "https://anymodel.org").rstrip("/")
CATALOG_URL = f"{BASE_URL}/v1/models"
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
USER_AGENT = "JAMP-StageBv2/1.0"
OUTPUT_DIR = pathlib.Path("artifacts/research/stage_b_v2")
FROZEN_BLOB = "0fee0e1c5c1a1548361965ac51eacdeba62bfe8a"

TARGETS = (
    {"model_id": "am/nemotron-3-ultra-550b-a55b", "task_id": "task5", "max_tokens": 4096},
    {"model_id": "ds/deepseek-v4-pro", "task_id": "task1", "max_tokens": 8192},
    {"model_id": "ds/deepseek-v4-pro", "task_id": "task2", "max_tokens": 8192},
    {"model_id": "ds/deepseek-v4-pro", "task_id": "task5", "max_tokens": 8192},
)
BLOCKED = ({
    "model_id": "cx/gpt-6-astra",
    "task_id": "task2",
    "reason": "Stage B v1 billing_status=AMBIGUOUS; estimated 624 units, actual debit UNKNOWN. No retry path exists.",
},)

TASK1_PROMPT = (
    "Дана последовательность a(n) = n² для n = 1, 2, 3, ...\n"
    "Задача: докажи формально, что для всех целых n ≥ 1 верно "
    "a(n+1) - a(n) = 2n + 1.\n"
    "Требуется: 1. Формальное доказательство. 2. Метод. "
    "3. Укажи, нужны ли дополнительные аксиомы."
)
TASK5_PROMPT = (
    "Предложи один механизм, снижающий вероятность галлюцинаций LLM "
    "при генерации кода без увеличения числа API-запросов.\n"
    "Укажи название, принцип работы (3–5 предложений), отличие от "
    "существующих подходов, проверяемый эксперимент и ограничения. "
    "Не заявляй эффективность без измерений."
)

def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def utc_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")

def valid_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )

def parse_coefficient(billing: dict[str, Any]) -> tuple[float, float] | None:
    value = billing.get("coefficient")
    if valid_number(value):
        return float(value), float(value)
    if isinstance(value, dict):
        input_value, output_value = value.get("input"), value.get("output")
        if valid_number(input_value) and valid_number(output_value):
            return float(input_value), float(output_value)
    return None

def resolve_coefficients(catalog: dict[str, Any], model_id: str) -> tuple[float, float] | None:
    rows = catalog.get("data") if isinstance(catalog, dict) else None
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == model_id]
    if len(matches) != 1 or not isinstance(matches[0].get("billing"), dict):
        return None
    return parse_coefficient(matches[0]["billing"])

def classify(http_status: int, body: dict[str, Any]) -> str:
    if http_status != 200:
        return f"HTTP_{http_status}"
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return "RESPONSE_EMPTY"
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    finish = choices[0].get("finish_reason")
    if not isinstance(content, str) or not content.strip():
        return "RESPONSE_EMPTY"
    if finish == "length":
        return "RESPONSE_TRUNCATED"
    if finish == "stop":
        return "RESPONSE_COMPLETE"
    return "RESPONSE_INCOMPLETE"

def build_task2_prompt(repo_root: pathlib.Path) -> str:
    paths = (
        repo_root / "scripts" / "g1_verify.py",
        repo_root / "tests" / "test_g1_verify.py",
    )
    contents = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"Required Task 2 source missing: {path}")
        contents.append(path.read_text(encoding="utf-8"))
    return (
        "Ниже два реальных файла из проверяемого коммита JAMP.\n\n"
        f"=== scripts/g1_verify.py ===\n{contents[0]}\n\n"
        f"=== tests/test_g1_verify.py ===\n{contents[1]}\n\n"
        "Найди конкретный воспроизводимый сценарий, в котором fail-closed "
        "логика g1_verify.py может вернуть PASS при нарушенном условии. "
        "Укажи минимальный сценарий, точные строки, причинную цепочку, "
        "необходимый тест-регрессию и минимальное изменение. Если дыры нет — "
        "обоснуй вывод по представленному коду."
    )

def get_prompt(task_id: str, repo_root: pathlib.Path) -> str:
    if task_id == "task1":
        return TASK1_PROMPT
    if task_id == "task5":
        return TASK5_PROMPT
    if task_id == "task2":
        return build_task2_prompt(repo_root)
    raise ValueError(f"Unknown task: {task_id}")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, new_url: str) -> None:
        return None

def http_request(url: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="GET" if payload is None else "POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    started = time.monotonic()
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=180) as response:
            raw = response.read()
            return {"http_status": response.status, "headers": dict(response.headers.items()),
                    "raw_body": raw, "transport_status": "COMPLETE",
                    "transport_error": None,
                    "latency_ms": round((time.monotonic() - started) * 1000)}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return {"http_status": exc.code, "headers": dict(exc.headers.items()) if exc.headers else {},
                "raw_body": raw, "transport_status": "HTTP_ERROR",
                "transport_error": None,
                "latency_ms": round((time.monotonic() - started) * 1000)}
    except http.client.IncompleteRead as exc:
        return {"http_status": None, "headers": {}, "raw_body": exc.partial or b"",
                "transport_status": "INCOMPLETE_READ", "transport_error": str(exc),
                "latency_ms": round((time.monotonic() - started) * 1000)}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"http_status": None, "headers": {}, "raw_body": b"",
                "transport_status": "TRANSPORT_ERROR",
                "transport_error": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.monotonic() - started) * 1000)}

def atomic_write_json(path: pathlib.Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as tmp:
        tmp.write(raw)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_name = tmp.name
    os.replace(temp_name, path)

def persist_raw(path: pathlib.Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())

def preflight(api_key: str, repo_root: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    response = http_request(CATALOG_URL, api_key)
    raw = response["raw_body"]
    if response["transport_status"] != "COMPLETE" or response["http_status"] != 200:
        raise RuntimeError(
            f"Catalog preflight failed: transport={response['transport_status']} "
            f"http={response['http_status']}; no model requests sent"
        )
    try:
        catalog = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Catalog response is not valid UTF-8 JSON; no model requests sent") from exc

    plan = []
    for target in TARGETS:
        coeffs = resolve_coefficients(catalog, target["model_id"])
        if coeffs is None:
            raise RuntimeError(f"Missing, ambiguous or invalid billing coefficient: {target['model_id']}")
        prompt = get_prompt(target["task_id"], repo_root)
        plan.append({
            **target,
            "input_coefficient": coeffs[0],
            "output_coefficient": coeffs[1],
            "prompt_sha256": sha256(prompt.encode("utf-8")),
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
        })
    return {
        "catalog_http_status": response["http_status"],
        "catalog_sha256": sha256(raw),
        "catalog_bytes": len(raw),
        "catalog_raw_base64": base64.b64encode(raw).decode("ascii"),
        "catalog_headers": response["headers"],
        "catalog_fetched_at": utc_now(),
    }, plan

def run(api_key: str, repo_root: pathlib.Path, catalog_record: dict[str, Any],\n        plan: list[dict[str, Any]]) -> int:
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir()):
        raise RuntimeError(f"Evidence directory already exists; refusing overwrite: {OUTPUT_DIR}")
    frozen_blob = None
    try:
        import subprocess
        frozen_blob = subprocess.check_output(
            ["git", "rev-parse", "HEAD:src/jamp/run.py"], cwd=repo_root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        raise RuntimeError("Cannot verify Frozen Core blob; no model requests sent")
    if frozen_blob != FROZEN_BLOB:
        raise RuntimeError(f"Frozen Core mismatch: {frozen_blob}; no model requests sent")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    catalog_raw = base64.b64decode(catalog_record.pop("catalog_raw_base64"))
    persist_raw(OUTPUT_DIR / "catalog_raw.json", catalog_raw)
    catalog_record["catalog_raw_file"] = "catalog_raw.json"
    catalog_record["catalog_raw_sha256"] = sha256(catalog_raw)
    state: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment": "JAMP_STAGE_B_V2_TARGETED",
        "status": "RUNNING",
        "started_at": utc_now(),
        "github_sha": os.getenv("GITHUB_SHA"),
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "frozen_core": {"expected_blob": FROZEN_BLOB, "observed_blob": frozen_blob,
                        "delta_zero": frozen_blob == FROZEN_BLOB},
        "catalog": catalog_record,
        "planned_requests": 4,
        "attempted_requests": 0,
        "blocked_targets": list(BLOCKED),
        "plan": plan,
        "results": [],
        "deepseek_outcome": "NOT_DETERMINED",
        "model_qualification": "NOT_STARTED",
        "routing_eligibility": "REFUSE",
    }
    manifest_path = OUTPUT_DIR / "run_manifest.json"
    atomic_write_json(manifest_path, state)

    for index, entry in enumerate(plan, start=1):
        prompt = get_prompt(entry["task_id"], repo_root)
        payload = {
            "model": entry["model_id"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": entry["max_tokens"],
            "temperature": 0,
        }
        response = http_request(CHAT_URL, api_key, payload)
        raw_name = f"{index:02d}_{entry['task_id']}_response.bin"
        persist_raw(OUTPUT_DIR / raw_name, response["raw_body"])
        record: dict[str, Any] = {
            "sequence": index, "model_id": entry["model_id"], "task_id": entry["task_id"],
            "requested_at": utc_now(), "max_tokens": entry["max_tokens"],
            "prompt_sha256": entry["prompt_sha256"],
            "prompt_utf8_bytes": entry["prompt_utf8_bytes"],
            "http_status": response["http_status"],
            "response_headers": response["headers"],
            "latency_ms": response["latency_ms"],
            "transport_status": response["transport_status"],
            "transport_error": response["transport_error"],
            "raw_response_file": raw_name,
            "raw_response_sha256": sha256(response["raw_body"]),
            "raw_response_bytes": len(response["raw_body"]),
            "billing_status": "UNKNOWN",
            "estimated_balance_debit_units": None,
            "status": "UNKNOWN",
        }
        if response["transport_status"] == "COMPLETE" and response["http_status"] == 200:
            try:
                body = json.loads(response["raw_body"].decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                record["status"] = "RESPONSE_INVALID"
            else:
                record["status"] = classify(200, body)
                usage = body.get("usage") if isinstance(body, dict) else None
                usage = usage if isinstance(usage, dict) else {}
                p, c = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if (isinstance(p, int) and not isinstance(p, bool) and p >= 0
                        and isinstance(c, int) and not isinstance(c, bool) and c >= 0):
                    record["usage"] = {"prompt_tokens": p, "completion_tokens": c}
                    record["estimated_balance_debit_units"] = (
                        p * entry["input_coefficient"] + c * entry["output_coefficient"]
                    )
                    record["billing_status"] = "USAGE_REPORTED"
                else:
                    record["billing_status"] = "UNKNOWN"
                choices = body.get("choices")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message")
                    record["assistant_content"] = msg.get("content") if isinstance(msg, dict) else None
                    record["finish_reason"] = choices[0].get("finish_reason")
        elif response["transport_status"] == "HTTP_ERROR":
            record["status"] = f"HTTP_{response['http_status']}"
        elif response["transport_status"] == "INCOMPLETE_READ":
            record["status"] = "INCOMPLETE_READ"
        else:
            record["status"] = "TRANSPORT_ERROR"

        state["attempted_requests"] += 1
        state["results"].append(record)
        atomic_write_json(manifest_path, state)
        if (response["transport_status"] != "COMPLETE" or response["http_status"] != 200\n                or record["billing_status"] == "UNKNOWN"):\n            state["stop_reason"] = (\n                "Transport, HTTP, or billing evidence failure; stopped fail-closed."\n            )\n            break
        if index < len(plan):
            time.sleep(60 if "nemotron" in entry["model_id"] else 5)

    deepseek = [r for r in state["results"] if r["model_id"] == "ds/deepseek-v4-pro"]
    if len(deepseek) == 3 and all(r["status"] == "RESPONSE_EMPTY" for r in deepseek):
        state["deepseek_outcome"] = "MODEL_INCOMPATIBLE_WITH_MAX_TOKENS_FORMAT"
    elif len(deepseek) == 3 and all(r["status"] == "RESPONSE_COMPLETE" for r in deepseek):
        state["deepseek_outcome"] = "SALVAGED"
    elif deepseek:
        state["deepseek_outcome"] = "INCONCLUSIVE"
    state["status"] = (
        "COMPLETED" if len(state["results"]) == 4
        and all(r["status"] == "RESPONSE_COMPLETE" for r in state["results"])
        else "PARTIAL_COMPLETED" if len(state["results"]) == 4
        else "STOPPED"
    )
    state["finished_at"] = utc_now()
    atomic_write_json(manifest_path, state)
    checksum_lines = [
        f"{sha256(path.read_bytes())}  {path.name}"
        for path in sorted(OUTPUT_DIR.iterdir())
        if path.is_file() and path.name != "checksums.sha256"
    ]
    (OUTPUT_DIR / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Experiment status: {state['status']}; evidence: {OUTPUT_DIR}")
    return 0 if state["status"] == "COMPLETED" else 1

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Send exactly the four planned model requests; default is dry-run.")
    args = parser.parse_args()
    api_key = os.getenv("ANYMODEL_API_KEY")
    if not api_key:
        print("REFUSE: ANYMODEL_API_KEY is required for catalog preflight.", file=sys.stderr)
        return 2
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    try:
        catalog, plan = preflight(api_key, repo_root)
    except Exception as exc:
        print(f"REFUSE: preflight failed: {exc}", file=sys.stderr)
        return 2
    print("Catalog preflight: VERIFIED response received; coefficients and exact target IDs validated.")
    print(f"Catalog SHA-256: {catalog['catalog_sha256']}")
    for row in plan:
        print(
            f"{row['model_id']} / {row['task_id']} / max_tokens={row['max_tokens']} "
            f"input_coeff={row['input_coefficient']} output_coeff={row['output_coefficient']} "
            f"prompt_sha256={row['prompt_sha256']}"
        )
    print("Blocked: cx/gpt-6-astra / task2 — billing AMBIGUOUS; no retry option.")
    if not args.execute:
        print("DRY-RUN: zero model requests sent. Use --execute only after explicit operator approval.")
        return 0
    try:
        return run(api_key, repo_root, catalog, plan)
    except Exception as exc:
        print(f"FAILED CLOSED: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
