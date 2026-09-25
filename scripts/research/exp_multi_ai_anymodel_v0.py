#!/usr/bin/env python3
"""EXP-MULTI-AI-V0: five free AnyModel sensors, one question, deterministic conflict matrix.

This experiment is deliberately outside src/jamp/run.py (Frozen Core).
It records raw model observations first, then derives a deterministic matrix
from the normalized structured answer field. No model is treated as an authority.
"""

from __future__ import annotations

import argparse
import hashlib
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
DEFAULT_QUESTION = "Is Pluto a planet? Answer under the International Astronomical Union (IAU) 2006 definition."
SYSTEM_PROMPT = (
    "You are an observation sensor in an evidence-first experiment. "
    "Do not defer to other models. Return ONLY valid JSON with exactly these keys: "
    "answer, evidence, uncertainty. "
    "answer must be a short normalized answer (for example: yes, no, unknown). "
    "evidence must briefly state the basis. uncertainty must be a short string."
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_answer(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.strip().lower().split())
    return value or None


def extract_json(text: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


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
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            elapsed_ms = round((time.monotonic() - started) * 1000, 3)
            data = json.loads(body)
            raw = data["choices"][0]["message"]["content"]
            parsed = extract_json(raw)
            answer = normalize_answer(parsed.get("answer")) if parsed else None
            return {
                "model": model,
                "status": "OBSERVED",
                "elapsed_ms": elapsed_ms,
                "raw_response": raw,
                "parsed": parsed,
                "normalized_answer": answer,
            }
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        detail = getattr(exc, "reason", str(exc))
        return {
            "model": model,
            "status": "ERROR",
            "elapsed_ms": elapsed_ms,
            "error": f"{type(exc).__name__}: {detail}",
        }


def build_matrix(observations: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = {}
    for left in observations:
        matrix[left["model"]] = {}
        for right in observations:
            if left["status"] != "OBSERVED" or right["status"] != "OBSERVED":
                relation = "UNKNOWN"
            elif left.get("normalized_answer") is None or right.get("normalized_answer") is None:
                relation = "UNKNOWN"
            elif left["normalized_answer"] == right["normalized_answer"]:
                relation = "AGREEMENT"
            else:
                relation = "CONFLICT"
            matrix[left["model"]][right["model"]] = relation
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--output", default="artifacts/research/exp_multi_ai_anymodel_v0.json")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    api_key = os.environ.get("ANYMODEL_API_KEY")
    if not api_key:
        print("ERROR: ANYMODEL_API_KEY is not set", file=sys.stderr)
        return 2

    manifest = {
        "experiment_id": "EXP-MULTI-AI-V0",
        "experiment_version": "v0",
        "provider": "AnyModel",
        "endpoint": BASE_URL,
        "models": MODELS,
        "question": args.question,
        "question_hash": sha256_text(args.question),
        "system_prompt_hash": sha256_text(SYSTEM_PROMPT),
        "temperature": 0,
        "observations": [],
        "matrix_rule": "AGREEMENT iff normalized_answer strings are equal; CONFLICT iff both observed and non-equal; otherwise UNKNOWN.",
    }
    for model in MODELS:
        manifest["observations"].append(call_model(api_key, model, args.question, args.timeout))
    manifest["conflict_matrix"] = build_matrix(manifest["observations"])
    manifest["summary"] = {
        "observed": sum(o["status"] == "OBSERVED" for o in manifest["observations"]),
        "errors": sum(o["status"] == "ERROR" for o in manifest["observations"]),
        "answers": sorted({o["normalized_answer"] for o in manifest["observations"] if o.get("normalized_answer")}),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    print(f"artifact={output}")
    return 0 if manifest["summary"]["observed"] == len(MODELS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
