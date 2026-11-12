#!/usr/bin/env python3
"""Run one pinned AnyModel expert review and preserve raw response evidence."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jamp.provider.anymodel import AnyModelChatExecutor, AnyModelError

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "experiments" / "expert-review"
CATALOG_URL = os.environ.get("ANYMODEL_CATALOG_URL", "https://anymodel.org/v1/models")
TIMEOUT_S = float(os.environ.get("ANYMODEL_TIMEOUT_S", "60"))
TEMPERATURE = 0.0
# Historical N3 evidence recorded each as AVAILABLE (3/3). Every dispatch
# rechecks the live catalog; historical availability is not a guarantee.
ROLE_MODELS = {
    "architect": "ag/claude-sonnet-4-6",
    "ux": "ag/gemini-3.7-flash-high",
    "auditor": "am/kimi-k3",
}
ROLE_PROMPTS = {
    "architect": "prompt_architect.md",
    "ux": "prompt_ux.md",
    "auditor": "prompt_auditor.md",
}


class ReviewError(RuntimeError):
    """A review could not produce complete, attributable evidence."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def timestamp_utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def roles_for_dispatch(role: str) -> list[str]:
    if role == "all":
        return list(ROLE_MODELS)
    if role not in ROLE_MODELS:
        raise ReviewError(f"Unsupported role: {role}")
    return [role]


def fetch_catalog(api_key: str) -> tuple[bytes, list[dict[str, Any]]]:
    request = Request(
        CATALOG_URL,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_S) as response:
            raw = response.read()
    except HTTPError as exc:
        raise ReviewError(f"Catalog request failed: HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError):
        raise ReviewError("Catalog transport failed") from None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ReviewError("Catalog response is not valid UTF-8 JSON") from None
    rows = decoded.get("data", decoded) if isinstance(decoded, dict) else decoded
    if not isinstance(rows, list):
        raise ReviewError("Catalog response has an unsupported shape")
    models = [
        row for row in rows
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    ]
    ids = [row["id"] for row in models]
    if len(ids) != len(set(ids)):
        raise ReviewError("Catalog contains duplicate model IDs")
    return raw, models


def load_prompt(role: str) -> bytes:
    filename = ROLE_PROMPTS.get(role)
    if filename is None:
        raise ReviewError(f"Unsupported role: {role}")
    try:
        return (PROMPTS_DIR / filename).read_bytes()
    except OSError:
        raise ReviewError(f"Prompt file unavailable for role: {role}") from None


def run_review(
    role: str,
    *,
    api_key: str,
    output_dir: pathlib.Path,
    catalog_fetcher=fetch_catalog,
    executor=None,
) -> dict[str, Any]:
    if role not in ROLE_MODELS:
        raise ReviewError(f"Unsupported role: {role}")
    role_dir = output_dir / role
    role_dir.mkdir(parents=True, exist_ok=True)
    if not api_key:
        raise ReviewError("ANYMODEL_API_KEY is required")
    model_id = ROLE_MODELS[role]
    prompt_bytes = load_prompt(role)
    try:
        prompt_text = prompt_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise ReviewError("Prompt is not valid UTF-8") from None

    catalog_raw, catalog_models = catalog_fetcher(api_key)
    matches = [row for row in catalog_models if row.get("id") == model_id]
    if len(matches) != 1:
        raise ReviewError(f"Pinned model is not uniquely present in live catalog: {model_id}")
    catalog_path = role_dir / "catalog_raw.json"
    catalog_path.write_bytes(catalog_raw)
    catalog_digest = sha256(catalog_path.read_bytes())

    client = executor or AnyModelChatExecutor(api_key, timeout=TIMEOUT_S)
    started_at = timestamp_utc()
    started = time.perf_counter()
    try:
        result = client(model_id, {"prompt": prompt_text})
    except AnyModelError as exc:
        raise ReviewError(f"AnyModel request failed: {type(exc).__name__}") from None
    except Exception as exc:
        raise ReviewError(f"Expert request failed: {type(exc).__name__}") from None
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    completed_at = timestamp_utc()

    if not isinstance(result, dict) or not isinstance(result.get("content"), str):
        raise ReviewError("AnyModel returned no textual completion")
    response_path = role_dir / "response.md"
    response_path.write_bytes(result["content"].encode("utf-8"))
    response_bytes = response_path.read_bytes()
    if not response_bytes:
        raise ReviewError("AnyModel returned an empty completion")

    provider_model_id = result.get("provider_model_id")
    if not isinstance(provider_model_id, str) or not provider_model_id.strip():
        provider_model_id = None
    metadata = {
        "schema_version": "jamp-expert-review-evidence-v1",
        "role": role,
        "provider": result.get("provider"),
        "requested_model_id": model_id,
        "provider_model_id": provider_model_id,
        "provider_response_id": result.get("provider_response_id"),
        "timestamp_utc": completed_at,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "prompt_sha256": sha256(prompt_bytes),
        "response_sha256": sha256(response_bytes),
        "catalog_sha256": catalog_digest,
        "temperature": TEMPERATURE,
        "elapsed_ms": elapsed_ms,
        "provider_identity_status": "OBSERVED" if provider_model_id else "UNKNOWN",
        "qualification": "NOT_EVALUATED",
    }
    (role_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if provider_model_id is None:
        raise ReviewError(
            "provider_model_id missing; response and UNKNOWN metadata preserved"
        )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=[*ROLE_MODELS, "all"])
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=pathlib.Path("artifacts/expert-review"),
    )
    args = parser.parse_args()
    current_role = None
    try:
        for current_role in roles_for_dispatch(args.role):
            metadata = run_review(
                current_role,
                api_key=os.environ.get("ANYMODEL_API_KEY", ""),
                output_dir=args.output_dir,
            )
            print(json.dumps({
                "role": current_role,
                "requested_model_id": metadata["requested_model_id"],
                "provider_model_id": metadata["provider_model_id"],
                "response_sha256": metadata["response_sha256"],
                "elapsed_ms": metadata["elapsed_ms"],
            }, sort_keys=True))
    except ReviewError as exc:
        if current_role is not None:
            failure_dir = args.output_dir / current_role
            failure_dir.mkdir(parents=True, exist_ok=True)
            (failure_dir / "failure.json").write_text(
                json.dumps({
                    "role": current_role,
                    "timestamp_utc": timestamp_utc(),
                    "state": "FAILED",
                    "error": str(exc),
                }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        raise SystemExit(str(exc)) from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
