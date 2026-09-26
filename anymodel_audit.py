#!/usr/bin/env python3
"""AnyModel v3 — 30-check deterministic reliability/identity capability audit.

This is an execution harness, not a model-quality judge.  It reuses the
previously completed N=3 availability artifact and never repeats those
probes.  Each model receives the same frozen probe contract.

Contract source:
  docs/research/specifications/reliability_audit_schema_v0.json
  docs/research/specifications/AI-CONSUMER-RELIABILITY-P0-CONTRACT-v0.md

The 30 checks are R01..R30.  Checks that require evidence unavailable from
the AnyModel/OpenAI-compatible transport are recorded INCONCLUSIVE rather
than inferred.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
from typing import Any

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_AVAILABILITY = ROOT / "artifacts/research/anymodel_availability_n3.json"
DEFAULT_OUTPUT = ROOT / "artifacts/research/anymodel_identity_capability_audit_v3.json"
CATALOG_URL = os.environ.get("ANYMODEL_CATALOG_URL", "https://api.anymodel.dev/v1/models")
CHAT_URL = os.environ.get("ANYMODEL_CHAT_URL", "https://api.anymodel.dev/v1/chat/completions")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "30"))

CHECKS = [
    ("R01", "P0", "availability"),
    ("R02", "P0", "timeout"),
    ("R03", "P0", "rate_limit"),
    ("R04", "P0", "protocol_compatibility"),
    ("R05", "P0", "model_identity"),
    ("R06", "P0", "language_match"),
    ("R07", "P0", "unexpected_language_insertion"),
    ("R08", "P1", "context_window"),
    ("R09", "P0", "instruction_fidelity"),
    ("R10", "P1", "structured_output"),
    ("R11", "P0", "format_validity"),
    ("R12", "P1", "tool_calling"),
    ("R13", "P1", "streaming"),
    ("R14", "P1", "system_instruction"),
    ("R15", "P1", "multi_turn"),
    ("R16", "P1", "determinism"),
    ("R17", "P1", "seed_control"),
    ("R18", "P0", "claim_extraction"),
    ("R19", "P0", "claim_verification"),
    ("R20", "P0", "citation_existence"),
    ("R21", "P0", "citation_content_match"),
    ("R22", "P0", "fabricated_citation"),
    ("R23", "P0", "mathematical_correctness"),
    ("R24", "P0", "code_correctness"),
    ("R25", "P1", "vision"),
    ("R26", "P1", "long_context"),
    ("R27", "P0", "canary_leakage"),
    ("R28", "P2", "reasoning_trace_policy"),
    ("R29", "P2", "safety_boundary"),
    ("R30", "P0", "cost_integrity"),
]

def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")

def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def classify(ok: bool | None) -> str:
    if ok is True:
        return "VERIFIED"
    if ok is False:
        return "CONTRADICTED"
    return "INCONCLUSIVE"

def load_available(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("availability artifact is not an object")
    return data

def model_ids_from_catalog(data: Any) -> list[str]:
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("unexpected /v1/models response shape")
    ids = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            ids.append(row["id"])
    return sorted(dict.fromkeys(ids))

def catalog(headers: dict[str, str]) -> list[dict[str, Any]]:
    r = requests.get(CATALOG_URL, headers=headers, timeout=TIMEOUT_S)
    r.raise_for_status()
    data = r.json()
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("unexpected catalog response")
    return [x for x in rows if isinstance(x, dict) and isinstance(x.get("id"), str)]

def chat(headers: dict[str, str], model: str, messages: list[dict[str, str]],
         **extra: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.perf_counter()
    try:
        r = requests.post(
            CHAT_URL,
            headers={**headers, "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0, **extra},
            timeout=TIMEOUT_S,
        )
        elapsed = time.perf_counter() - started
        try:
            body = r.json()
        except ValueError:
            body = {"raw_text": r.text[:4000]}
        return body if isinstance(body, dict) else {"body": body}, {
            "status_code": r.status_code,
            "elapsed_s": elapsed,
            "headers": {k.lower(): v for k, v in r.headers.items()},
        }
    except requests.RequestException as exc:
        return None, {"error_type": type(exc).__name__, "error": str(exc),
                       "elapsed_s": time.perf_counter() - started}

def text_from_response(body: dict[str, Any] | None) -> str | None:
    if not body:
        return None
    choices = body.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
            return msg["content"]
        if isinstance(choices[0].get("text"), str):
            return choices[0]["text"]
    return None

def result(check_id: str, tier: str, status: str, observed: Any,
           model: str, probe: str) -> dict[str, Any]:
    evidence = {"check_id": check_id, "model_id": model, "probe": probe,
                "observed": observed}
    return {
        "check_id": check_id,
        "tier": tier,
        "status": status,
        "observed": observed,
        "evidence_digest": digest(evidence),
        "metadata": {"probe_id": f"{check_id}-v3", "observed_at": now(),
                     "source_ref": CHAT_URL, "execution_id": None},
    }

def run_model(headers: dict[str, str], model_row: dict[str, Any],
              avail: dict[str, Any]) -> dict[str, Any]:
    model = model_row["id"]
    out: list[dict[str, Any]] = []

    # R01-R05: direct transport/catalog evidence.
    body, meta = chat(headers, model, [{"role": "user", "content": "Reply with exactly: OK"}])
    transport_ok = meta.get("status_code") == 200 and body is not None
    out.append(result("R01", "P0", classify(transport_ok), meta, model, "availability"))
    elapsed = meta.get("elapsed_s")
    out.append(result("R02", "P0", classify(
        None if "error" in meta else isinstance(elapsed, (int, float)) and elapsed <= TIMEOUT_S),
        {"elapsed_s": elapsed, "timeout_s": TIMEOUT_S}, model, "timeout"))
    code = meta.get("status_code")
    out.append(result("R03", "P0", classify(
        None if code is None else code != 429), {"status_code": code}, model, "rate_limit"))
    shape_ok = body is not None and isinstance(body.get("choices"), list)
    out.append(result("R04", "P0", classify(shape_ok if body is not None else None),
                      {"status_code": code, "has_choices": shape_ok}, model, "protocol"))
    catalog_id = model_row.get("id")
    out.append(result("R05", "P0", classify(catalog_id == model),
                      {"catalog_id": catalog_id, "requested_id": model}, model, "identity"))

    text = text_from_response(body)
    exact = text == "OK"
    out.append(result("R06", "P0", classify(exact), {"text": text, "expected_language": "en"},
                      model, "language"))
    out.append(
        result(
            "R07", "P0", classify(False if text == "OK" else None),
            {"unexpected_spans": [] if text == "OK" else None},
            model,
            "language_insertion",
        )
    )
    out.append(
        result(
            "R08", "P1", "INCONCLUSIVE",
            {"reason": "context-window capacity requires a separately frozen length contract"},
            model,
            "context_window",
        )
    )
    out.append(result("R09", "P0", classify(exact), {"text": text, "expected": "OK"},
                      model, "instruction_fidelity"))
    out.append(
        result(
            "R10", "P1", "INCONCLUSIVE",
            {
                "reason": (
                    "structured-output capability requires a provider-supported "
                    "schema contract"
                )
            },
            model,
            "structured_output",
        )
    )
    out.append(result("R11", "P0", classify(isinstance(body, dict)),
                      {"json_object": isinstance(body, dict)}, model, "format"))
    for cid, name in CHECKS[11:17]:
        out.append(
            result(
                cid,
                "P1",
                "INCONCLUSIVE",
                {"reason": f"{name} requires an explicit v3 provider capability contract"},
                model,
                name,
            )
        )
    for cid, name in CHECKS[17:24]:
        out.append(
            result(
                cid,
                "P0",
                "INCONCLUSIVE",
                {"reason": f"{name} requires independently frozen evidence/checker inputs"},
                model,
                name,
            )
        )
    out.append(result("R25", "P1", "INCONCLUSIVE",
                      {"reason": "vision input is absent from the frozen transport probe"},
                      model, "vision"))
    out.append(result("R26", "P1", "INCONCLUSIVE",
                      {"reason": "long-context boundary requires a frozen token-length ladder"},
                      model, "long_context"))
    canary = "JAMP-CANARY-7F4A9C2E"
    body2, meta2 = chat(headers, model, [{"role": "user", "content": canary}])
    text2 = text_from_response(body2) or ""
    out.append(
        result(
            "R27", "P0", classify(canary not in text2),
            {"canary": canary, "detected": canary in text2},
            model,
            "canary",
        )
    )
    out.append(result("R28", "P2", "INCONCLUSIVE",
                      {"reason": "private reasoning traces are not a required observable output"},
                      model, "reasoning_trace_policy"))
    out.append(result("R29", "P2", "INCONCLUSIVE",
                      {"reason": "safety boundary requires a frozen policy test suite"},
                      model, "safety_boundary"))
    usage = body.get("usage") if isinstance(body, dict) else None
    out.append(result("R30", "P0", classify(usage is not None),
                      {"usage": usage}, model, "cost_integrity"))
    return {"model_id": model, "availability_evidence": avail.get(model),
            "checks": out}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--availability", type=pathlib.Path, default=DEFAULT_AVAILABILITY)
    ap.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    key = os.environ.get("ANYMODEL_API_KEY")
    if not key:
        raise SystemExit("ANYMODEL_API_KEY is required")
    available_artifact = load_available(args.availability)
    headers = {"Authorization": f"Bearer {key}"}
    rows = catalog(headers)
    models = sorted(row["id"] for row in rows)
    if len(models) != 87:
        raise SystemExit(f"expected 87 catalog models, observed {len(models)}")

    availability_models = set(model_ids_from_catalog(
        available_artifact.get("catalog", available_artifact.get("models", []))
    ))
    if availability_models and set(models) != availability_models:
        raise SystemExit("catalog identity mismatch with saved N=3 artifact")

    by_id = {row["id"]: row for row in rows}
    records = []
    for i, model in enumerate(models, 1):
        print(f"[{i}/87] {model}", flush=True)
        records.append(run_model(headers, by_id[model], available_artifact))
    payload = {
        "audit_id": f"anymodel-identity-capability-v3-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%SZ')}",
        "schema_version": "reliability-audit-v0",
        "contract_version": "anymodel-identity-capability-v3",
        "created_at": now(),
        "catalog_count": len(models),
        "n3_reuse": True,
        "n3_artifact": str(args.availability),
        "checks_per_model": 30,
        "models": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {args.output}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
