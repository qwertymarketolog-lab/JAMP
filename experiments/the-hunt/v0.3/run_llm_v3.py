"""Run one pinned Groq model over the fixed Hunt v0.3 prompt cohort.

Temperature is sent explicitly as 0.7 through an isolated HTTP client. The
production JAMP Groq adapter and its temperature default are not modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

TEMPERATURE = 0.7
TIMEOUT_SECONDS = 45
USER_AGENT = "JAMP-The-Hunt-v0.3-Experiment"


def _read_prompts(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("prompts file must be a JSON object")
    samples = payload.get("samples")
    if not isinstance(samples, list):
        raise ValueError("prompts file must contain a samples list")
    if len(samples) != 100:
        raise ValueError("v0.3 requires exactly 100 prompts")
    return payload, raw


def _parse_completion(content: str) -> tuple[str | None, str | None]:
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(decoded, dict):
        return None, None
    package_name = decoded.get("package_name")
    code = decoded.get("code")
    if not isinstance(package_name, str) or not isinstance(code, str):
        return None, None
    return package_name, code


def _call_groq(
    *, api_key: str, endpoint: str, model_id: str, prompt: str, max_tokens: int
) -> tuple[dict[str, object] | None, str | None]:
    body = json.dumps(
        {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": TEMPERATURE,
            "max_tokens": max_tokens,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except HTTPError as exc:
        return None, f"HTTP_{exc.code}"
    except (URLError, TimeoutError, OSError) as exc:
        return None, type(exc).__name__
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "INVALID_PROVIDER_JSON"
    if not isinstance(decoded, dict):
        return None, "INVALID_PROVIDER_RESPONSE"
    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None, "MISSING_COMPLETION"
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return None, "MISSING_COMPLETION_CONTENT"
    return {
        "content": content,
        "provider_response_id": decoded.get("id"),
        "provider_model_id": decoded.get("model"),
    }, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=Path("prompts.json"))
    parser.add_argument("--responses", type=Path, default=Path("llm_responses_v3.json"))
    parser.add_argument("--manifest", type=Path, default=Path("generation_manifest.json"))
    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY", "")
    model_id = os.environ.get("GROQ_MODEL", "").strip()
    base_url = os.environ.get(
        "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
    ).rstrip("/")
    endpoint = os.environ.get("GROQ_CHAT_URL", f"{base_url}/chat/completions")
    max_tokens = int(os.environ.get("GROQ_MAX_TOKENS", "1024"))
    parsed_endpoint = urlparse(endpoint)
    parsed_base = urlparse(base_url)
    if not api_key:
        raise SystemExit("GROQ_API_KEY is required")
    if not model_id:
        raise SystemExit("GROQ_MODEL is required; model identity must be pinned")
    if parsed_endpoint.scheme != "https" or not parsed_endpoint.hostname:
        raise SystemExit("Groq endpoint must be an HTTPS URL")
    if parsed_base.scheme != "https" or not parsed_base.hostname:
        raise SystemExit("Groq base URL must be an HTTPS URL")
    if (
        parsed_endpoint.username
        or parsed_endpoint.password
        or parsed_endpoint.query
        or parsed_base.username
        or parsed_base.password
        or parsed_base.query
    ):
        raise SystemExit("Groq endpoint must not contain credentials or query secrets")
    if max_tokens <= 0:
        raise SystemExit("GROQ_MAX_TOKENS must be positive")

    prompts, raw_prompts = _read_prompts(args.prompts)
    samples = prompts["samples"]
    if not isinstance(samples, list):
        raise ValueError("prompts file samples must be a list")
    prompt_hash = hashlib.sha256(raw_prompts).hexdigest()
    started_at = datetime.now(UTC).isoformat()
    results: list[dict[str, object]] = []
    provider_model_ids: set[str] = set()

    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("each prompt row must be a JSON object")
        sample_id = sample.get("sample_id")
        prompt = sample.get("prompt")
        package_name = sample.get("package_name")
        if not all(
            isinstance(value, str) and value
            for value in (sample_id, prompt, package_name)
        ):
            raise ValueError("each prompt requires sample_id, package_name, and prompt")
        request_timestamp = datetime.now(UTC).isoformat()
        response, failure = _call_groq(
            api_key=api_key,
            endpoint=endpoint,
            model_id=model_id,
            prompt=prompt,
            max_tokens=max_tokens,
        )
        if failure or response is None:
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": package_name,
                    "prompt": prompt,
                    "request_status": "FAILED",
                    "failure_reason": failure or "unknown_provider_failure",
                    "request_timestamp_utc": request_timestamp,
                }
            )
            continue

        returned_model = response.get("provider_model_id")
        if isinstance(returned_model, str) and returned_model:
            provider_model_ids.add(returned_model)
        content = response.get("content")
        if not isinstance(content, str):
            results.append(
                {
                    "sample_id": sample_id,
                    "package_name": package_name,
                    "prompt": prompt,
                    "request_status": "MALFORMED_RESPONSE",
                    "failure_reason": "provider_content_not_text",
                    "request_timestamp_utc": request_timestamp,
                }
            )
            continue
        response_package, code = _parse_completion(content)
        status = "SUCCESS"
        failure_reason = None
        if response_package != package_name or code is None or not code.strip():
            status = "MALFORMED_RESPONSE"
            failure_reason = "completion_not_valid_expected_json"
        if returned_model != model_id:
            status = "MODEL_ID_MISMATCH"
            failure_reason = "provider_returned_model_differs_from_requested_model"
        results.append(
            {
                "sample_id": sample_id,
                "package_name": package_name,
                "prompt": prompt,
                "request_status": status,
                "failure_reason": failure_reason,
                "request_timestamp_utc": request_timestamp,
                "provider_response_id": response.get("provider_response_id"),
                "provider_model_id": returned_model,
                "content": content,
                "code": code,
            }
        )

    response_payload = {
        "schema_version": "jamp-hunt-llm-responses-v0.3",
        "evidence_class": "LIVE_GROQ_GENERATIONS",
        "samples": results,
    }
    args.responses.parent.mkdir(parents=True, exist_ok=True)
    response_bytes = (
        json.dumps(response_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    args.responses.write_bytes(response_bytes)
    response_hash = hashlib.sha256(response_bytes).hexdigest()
    successful = sum(item["request_status"] == "SUCCESS" for item in results)
    manifest = {
        "schema_version": "jamp-hunt-generation-manifest-v0.3",
        "experiment_id": f"hunt-v03-{started_at}",
        "evaluation_mode": "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY",
        "provider_name": "groq",
        "provider_base_url": base_url,
        "provider_endpoint": endpoint,
        "requested_model_id": model_id,
        "provider_model_id": (
            next(iter(provider_model_ids)) if len(provider_model_ids) == 1 else None
        ),
        "provider_model_ids_observed": sorted(provider_model_ids),
        "temperature": TEMPERATURE,
        "max_completion_tokens": max_tokens,
        "prompt_dataset_sha256": prompt_hash,
        "generation_timestamp_utc": started_at,
        "completion_timestamp_utc": datetime.now(UTC).isoformat(),
        "successful_requests": successful,
        "failed_requests": len(results) - successful,
        "request_count": len(results),
        "llm_responses_sha256": response_hash,
        "llm_responses_file": args.responses.name,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "provider": "groq",
                "requested_model_id": model_id,
                "temperature": TEMPERATURE,
                "request_count": len(results),
                "successful_requests": successful,
                "failed_requests": len(results) - successful,
                "llm_responses_sha256": response_hash,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
