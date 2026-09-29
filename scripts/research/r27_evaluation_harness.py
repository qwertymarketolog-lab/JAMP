#!/usr/bin/env python3
"""Deterministic R27 evaluation harness implementing Contract v1.1."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

PARAM_ACCEPTED = "PARAM_ACCEPTED"
PARAM_TRUNCATED = "PARAM_TRUNCATED"
PARAM_REJECTED = "PARAM_REJECTED"
PARAM_UNRESOLVED = "PARAM_UNRESOLVED"
QUALIFIED = "QUALIFIED"
FAILED = "FAILED"
INCONCLUSIVE = "INCONCLUSIVE"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
R28_CANDIDATE = "R28_CANDIDATE"
HOLD = "HOLD"

FROZEN_PARAMS = {
    "temperature": 0.0,
    "top_p": 1.0,
    "max_tokens": 256,
    "stream": False,
}
TIMEOUT_S = 30.0
EXPECTED_R27_MODELS = 17

VECTORS = {
    "E01": "Reply with exactly: JAMP-E01-OK",
    "E02": ('Return exactly this JSON object and no other text:\n{"jamp_e02":"OK","value":17}'),
    "E03": "Calculate exactly: (137 * 29) - 411.\nReply with only the integer.",
    "E04": "What is the chemical symbol for gold?\nReply with only the chemical symbol.",
    "E05": "\n".join(
        (
            "Remember this identifier exactly: JAMP-E05-7C91.",
            "Now reply with only that identifier.",
        )
    ),
    "E06": ("Reply with exactly this string and nothing else:\nJAMP-E06-ÄΩЖ中🚀"),
    "E07": ("Reply with exactly one line in this format:\nJAMP-E07:<integer>\nUse the integer 42."),
}


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def parameter_resolution(response: Any, http_status: int | None) -> tuple[str, dict[str, Any]]:
    diagnostics = {
        "output_budget_status": PARAM_UNRESOLVED,
        "raw_finish_reason": None,
        "http_status_code": http_status,
        "prompt_tokens": None,
        "completion_tokens": None,
        "reasoning_tokens": None,
    }

    if (
        http_status is None
        or http_status >= 500
        or http_status in {401, 403, 404, 408, 409, 422, 429}
    ):
        return PARAM_UNRESOLVED, diagnostics

    if http_status == 400:
        error = response.get("error", {}) if isinstance(response, dict) else {}
        text = json.dumps(error, ensure_ascii=False).lower()
        explicit = str(error.get("param", "")).lower() == "max_tokens"
        explicit = explicit or str(error.get("parameter", "")).lower() == "max_tokens"
        explicit = explicit or (
            "max_tokens" in text
            and any(word in text for word in ("invalid", "unsupported", "reject"))
        )
        status = PARAM_REJECTED if explicit else PARAM_UNRESOLVED
        return status, diagnostics | {"parameter_error": error}

    if http_status != 200 or not isinstance(response, dict):
        return PARAM_UNRESOLVED, diagnostics

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return PARAM_UNRESOLVED, diagnostics
    first = choices[0]
    if not isinstance(first, dict):
        return PARAM_UNRESOLVED, diagnostics

    reason = first.get("finish_reason")
    diagnostics["raw_finish_reason"] = reason

    usage = response.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    diagnostics["prompt_tokens"] = usage.get("prompt_tokens")
    diagnostics["completion_tokens"] = usage.get("completion_tokens")

    details = usage.get("completion_tokens_details")
    if isinstance(details, dict):
        diagnostics["reasoning_tokens"] = details.get("reasoning_tokens")

    if reason == "stop":
        return PARAM_ACCEPTED, diagnostics
    if reason == "length":
        return PARAM_TRUNCATED, diagnostics
    return PARAM_UNRESOLVED, diagnostics


def response_content(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    return None


def check(test_id: str, output: str) -> str:
    expected = {
        "E01": "JAMP-E01-OK",
        "E03": "3562",
        "E04": "Au",
        "E05": "JAMP-E05-7C91",
        "E06": "JAMP-E06-ÄΩЖ中🚀",
    }
    if test_id in expected:
        return "PASS" if output == expected[test_id] else "FAIL"
    if test_id == "E02":
        try:
            return "PASS" if json.loads(output) == {"jamp_e02": "OK", "value": 17} else "FAIL"
        except (TypeError, ValueError):
            return "FAIL"
    return "PASS" if re.fullmatch(r"JAMP-E07:42", output) else "FAIL"


def aggregate(
    runtime_pass: bool,
    parameter_state: str,
    tests: dict[str, str],
    e08: str,
    contract_violation: bool = False,
) -> str:
    if contract_violation or parameter_state == PARAM_REJECTED:
        return CONTRACT_VIOLATION
    if parameter_state != PARAM_ACCEPTED or not runtime_pass:
        if parameter_state in {PARAM_TRUNCATED, PARAM_UNRESOLVED}:
            return INCONCLUSIVE
        return FAILED
    if any(value != "PASS" for value in tests.values()):
        return FAILED
    if e08 == "FAIL":
        return FAILED
    if e08 == "INCONCLUSIVE":
        return INCONCLUSIVE
    return QUALIFIED


def r28_filter(
    r27_valid: bool,
    runtime_pass: bool,
    parameter_state: str,
    tests: dict[str, str],
    e08: str,
    aggregate_state: str,
) -> str:
    if aggregate_state == CONTRACT_VIOLATION or parameter_state == PARAM_REJECTED:
        return CONTRACT_VIOLATION
    if not r27_valid or not runtime_pass:
        return HOLD if parameter_state == PARAM_ACCEPTED else INCONCLUSIVE
    if parameter_state != PARAM_ACCEPTED:
        return INCONCLUSIVE
    if (
        all(value == "PASS" for value in tests.values())
        and e08 != "FAIL"
        and aggregate_state == QUALIFIED
    ):
        return R28_CANDIDATE
    return HOLD if aggregate_state == FAILED else INCONCLUSIVE


def build_request(model: str, prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        **FROZEN_PARAMS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("artifacts/research/r27_provenance_probe.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/research/r27_evaluation_v1.json"),
    )
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    models = [record["model_id"] for record in source.get("records", [])]
    if len(models) != EXPECTED_R27_MODELS or len(set(models)) != EXPECTED_R27_MODELS:
        raise SystemExit("R27 source cardinality/uniqueness violation")

    if not args.execute:
        print("STATIC HARNESS CHECK: PASS")
        print(f"R27 models: {len(models)}")
        print("Runtime execution: NOT STARTED")
        return 0

    import os

    import requests

    key = os.environ.get("ANYMODEL_API_KEY")
    if not key:
        raise SystemExit("ANYMODEL_API_KEY is required for --execute")

    targets = args.models or models
    records = []

    for model in targets:
        model_record = {"model_id": model, "tests": {}}

        for test_id, prompt in VECTORS.items():
            request = build_request(model, prompt)
            started = time.perf_counter()
            try:
                response = requests.post(
                    "https://anymodel.org/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=request,
                    timeout=TIMEOUT_S,
                )
                elapsed = time.perf_counter() - started
                try:
                    body = response.json()
                except ValueError:
                    body = None

                state, diagnostics = parameter_resolution(body, response.status_code)
                result = {
                    "status": state,
                    "parameter_resolution": diagnostics,
                    "elapsed_s": elapsed,
                    "input_digest": sha256_text(prompt),
                }

                if state == PARAM_ACCEPTED:
                    output = response_content(body)
                    returned_model = body.get("model") if isinstance(body, dict) else None
                    if returned_model != model:
                        result["status"] = CONTRACT_VIOLATION
                        result["model_identity"] = {
                            "requested": model,
                            "returned": returned_model,
                        }
                    elif output is None:
                        result["status"] = INCONCLUSIVE
                    else:
                        result["status"] = check(test_id, output)
                        result["observed_output_digest"] = sha256_text(output)

                model_record["tests"][test_id] = result
            except requests.RequestException as exc:
                model_record["tests"][test_id] = {
                    "status": INCONCLUSIVE,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }

        model_record["e08"] = "INCONCLUSIVE"
        test_states = {key: value["status"] for key, value in model_record["tests"].items()}
        accepted = all(
            value.get("parameter_resolution", {}).get("output_budget_status") == PARAM_ACCEPTED
            for value in model_record["tests"].values()
        )
        parameter_state = PARAM_ACCEPTED if accepted else PARAM_UNRESOLVED
        runtime_pass = accepted and all(value == "PASS" for value in test_states.values())
        model_record["aggregate_state"] = aggregate(
            runtime_pass, parameter_state, test_states, model_record["e08"]
        )
        model_record["candidate_state"] = r28_filter(
            True,
            runtime_pass,
            parameter_state,
            test_states,
            model_record["e08"],
            model_record["aggregate_state"],
        )
        records.append(model_record)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_id": "R27-EVALUATION-v1.1",
        "inference_parameters": FROZEN_PARAMS,
        "models": records,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
