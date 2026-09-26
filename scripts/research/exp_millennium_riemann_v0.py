#!/usr/bin/env python3
"""EXP-MILLENNIUM-RIEMANN-V0: five independent AI sensors for the Riemann Hypothesis."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = "https://anymodel.org/v1/chat/completions"
MODELS = [
    "am/diffusiongemma-26b-a4b-it",
    "am/gpt-oss-20b",
    "am/laguna-xs-2.1",
    "am/llama-3.2-11b-vision-instruct",
    "am/mistral-nemotron",
]
DEFAULT_QUESTION = (
    "Prove or disprove the Riemann Hypothesis: every non-trivial zero of "
    "the Riemann zeta function zeta(s) has real part 1/2."
)
SYSTEM_PROMPT = (
    """You are an independent mathematical research sensor in an evidence-first """
    """experiment.
Do not defer to other models. Do not claim a theorem merely because an argument is plausible.
Return ONLY valid JSON with exactly these keys:
status, claim, key_lemmas, critical_steps, unproved_dependencies, evidence, uncertainty.
status must be exactly one of: PROOF_CLAIM, DISPROOF_CLAIM, UNKNOWN.
If you cannot establish a complete proof or disproof, return UNKNOWN.
Distinguish established results from your own proposed argument.
List every critical step and every unproved dependency explicitly.
Do not treat model confidence, consensus, or numerical evidence as a proof.
"""
)

VALID_STATUSES = {"PROOF_CLAIM", "DISPROOF_CLAIM", "UNKNOWN"}
EXPECTED_KEYS = {
    "status",
    "claim",
    "key_lemmas",
    "critical_steps",
    "unproved_dependencies",
    "evidence",
    "uncertainty",
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_response(text: str) -> str:
    """Normalize representation only; never repair semantic values or types."""
    if not isinstance(text, str):
        return text
    return text.replace("\u00a0", " ").strip()


def extract_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(text, str):
        return None, "PARSER_FAILURE: response content is not a string"
    normalized = normalize_response(text)
    try:
        obj = json.loads(normalized)
        return (obj if isinstance(obj, dict) else None), (
            None if isinstance(obj, dict) else "PARSER_FAILURE: top-level JSON is not an object"
        )
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", normalized, flags=re.DOTALL)
        if not match:
            return None, "PARSER_FAILURE: no JSON object found"
        try:
            obj = json.loads(match.group(0))
            return (obj if isinstance(obj, dict) else None), (
                None
                if isinstance(obj, dict)
                else "PARSER_FAILURE: extracted JSON is not an object"
            )
        except json.JSONDecodeError as exc:
            return None, f"PARSER_FAILURE: {type(exc).__name__}: {exc}"


def validate_observation(parsed: dict[str, Any] | None) -> dict[str, Any]:
    if parsed is None:
        return {"valid": False, "error_category": "PARSER_FAILURE", "reason": "no parsed object"}

    extra = sorted(set(parsed) - EXPECTED_KEYS)
    missing = sorted(EXPECTED_KEYS - set(parsed))
    if extra or missing:
        return {
            "valid": False,
            "error_category": "SCHEMA_VIOLATION",
            "reason": "key_set_mismatch",
            "missing_keys": missing,
            "extra_keys": extra,
        }

    if parsed["status"] not in VALID_STATUSES:
        return {
            "valid": False,
            "error_category": "SCHEMA_VIOLATION",
            "reason": "invalid_enum",
            "field": "status",
            "expected": sorted(VALID_STATUSES),
            "actual": parsed["status"],
        }

    for key in ("claim", "uncertainty"):
        if not isinstance(parsed[key], str):
            return {
                "valid": False,
                "error_category": "SCHEMA_VIOLATION",
                "reason": "invalid_type",
                "field": key,
                "expected": "string",
                "actual": type(parsed[key]).__name__,
            }

    for key in ("key_lemmas", "critical_steps", "unproved_dependencies", "evidence"):
        if not isinstance(parsed[key], list) or not all(
            isinstance(item, str) for item in parsed[key]
        ):
            return {
                "valid": False,
                "error_category": "SCHEMA_VIOLATION",
                "reason": "invalid_type",
                "field": key,
                "expected": "list[string]",
                "actual": type(parsed[key]).__name__,
            }

    return {"valid": True, "error_category": None}


def call_model(api_key: str, model: str, question: str, timeout: int) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0,
    }
    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            try:
                body = response.read().decode("utf-8")
            except http.client.IncompleteRead as exc:
                elapsed_ms = round((time.monotonic() - started) * 1000, 3)
                return {
                    "model": model,
                    "status": "ERROR",
                    "error_category": "TRANSPORT_FAILURE",
                    "elapsed_ms": elapsed_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                    "partial_response_bytes": len(exc.partial),
                }

            elapsed_ms = round((time.monotonic() - started) * 1000, 3)
            try:
                data = json.loads(normalize_response(body))
                raw = data["choices"][0]["message"]["content"]
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                return {
                    "model": model,
                    "status": "ERROR",
                    "error_category": "PARSER_FAILURE",
                    "elapsed_ms": elapsed_ms,
                    "error": f"{type(exc).__name__}: {exc}",
                    "raw_response": body,
                }

            parsed, parser_error = extract_json(raw)
            normalized_response = normalize_response(raw)
            validation = validate_observation(parsed)
            if parser_error:
                return {
                    "model": model,
                    "status": "ERROR",
                    "error_category": "PARSER_FAILURE",
                    "elapsed_ms": elapsed_ms,
                    "error": parser_error,
                    "raw_response": raw,
                    "normalized_response": normalized_response,
                    "parsed": parsed,
                    "strict_schema_validation": validation,
                }

            if not validation["valid"]:
                return {
                    "model": model,
                    "status": "ERROR",
                    "error_category": "SCHEMA_VIOLATION",
                    "elapsed_ms": elapsed_ms,
                    "error": "strict schema validation failed",
                    "raw_response": raw,
                    "normalized_response": normalized_response,
                    "parsed": parsed,
                    "strict_schema_validation": validation,
                }

            return {
                "model": model,
                "status": "OBSERVED",
                "elapsed_ms": elapsed_ms,
                "raw_response": raw,
                "normalized_response": normalized_response,
                "parsed": parsed,
                "strict_schema_validation": validation,
                "declared_status": parsed["status"],
            }
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        http.client.RemoteDisconnected,
        KeyError,
        IndexError,
    ) as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        detail = getattr(exc, "reason", str(exc))
        return {
            "model": model,
            "status": "ERROR",
            "error_category": "TRANSPORT_FAILURE",
            "elapsed_ms": elapsed_ms,
            "error": f"{type(exc).__name__}: {detail}",
        }


def build_status_matrix(observations: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = {}
    for left in observations:
        matrix[left["model"]] = {}
        for right in observations:
            if left["status"] != "OBSERVED" or right["status"] != "OBSERVED":
                relation = "UNKNOWN"
            elif left["declared_status"] == right["declared_status"]:
                relation = "AGREEMENT"
            else:
                relation = "CONFLICT"
            matrix[left["model"]][right["model"]] = relation
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--output",
        default="artifacts/research/exp_millennium_riemann_v0.json",
    )
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        print("ERROR: ANYMODEL_API_KEY is not set", file=sys.stderr)
        return 2

    manifest: dict[str, Any] = {
        "experiment_id": "EXP-MILLENNIUM-RIEMANN-V0",
        "experiment_version": "v0",
        "provider": "AnyModel",
        "models": MODELS,
        "question": args.question,
        "question_hash": sha256_text(args.question),
        "system_prompt_hash": sha256_text(SYSTEM_PROMPT),
        "temperature": 0,
        "response_contract_version": "v0.1-hardening",
        "normalization_rule": (
            "Representation-only normalization: replace U+00A0 with ASCII space "
            "and trim outer whitespace. No semantic enum repair or type coercion."
        ),
        "observations": [],
        "arbitration_rule": (
            "AGREEMENT iff both observations are valid and declared_status strings "
            "are equal; CONFLICT iff both are valid and declared_status strings differ; "
            "otherwise UNKNOWN."
        ),
        "verification_rule": (
            "A PROOF_CLAIM or DISPROOF_CLAIM is UNVERIFIED_CLAIM until independently "
            "verified; model confidence and majority do not establish mathematical truth."
        ),
    }

    for model in MODELS:
        manifest["observations"].append(
            call_model(api_key, model, args.question, args.timeout)
        )

    manifest["status_matrix"] = build_status_matrix(manifest["observations"])
    manifest["summary"] = {
        "observed": sum(
            observation["status"] == "OBSERVED"
            for observation in manifest["observations"]
        ),
        "errors": sum(
            observation["status"] == "ERROR"
            for observation in manifest["observations"]
        ),
        "error_categories": {
            category: sum(
                observation.get("error_category") == category
                for observation in manifest["observations"]
            )
            for category in (
                "TRANSPORT_FAILURE",
                "PARSER_FAILURE",
                "SCHEMA_VIOLATION",
            )
        },
        "declared_statuses": sorted(
            {
                observation["declared_status"]
                for observation in manifest["observations"]
                if observation["status"] == "OBSERVED"
            }
        ),
        "verification_status": "UNVERIFIED_CLAIMS_ONLY",
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    print(f"artifact={output}")
    return 0 if manifest["summary"]["observed"] == len(MODELS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
