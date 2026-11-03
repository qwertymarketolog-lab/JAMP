"""Run pinned provider models over the fixed Hunt v0.3 prompt cohort."""
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
PROVIDER_DEFAULTS = {
    "groq": "https://api.groq.com/openai/v1",
    "anymodel": "https://anymodel.org/v1",
}

def _read_prompts(path: Path):
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("samples"), list)
        or len(payload["samples"]) != 100
    ):
        raise ValueError("v0.3 source dataset must contain exactly 100 prompts")
    return payload, raw

def _parse_completion(content: str):
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(decoded, dict):
        return None, None
    package_name, code = decoded.get("package_name"), decoded.get("code")
    if not isinstance(package_name, str) or not isinstance(code, str):
        return None, None
    return package_name, code

def _call_openai_compatible(*, api_key, endpoint, model_id, prompt, max_tokens):
    body = json.dumps({
        "model": model_id, "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE, "max_tokens": max_tokens,
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(endpoint, data=body, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "Accept": "application/json", "User-Agent": USER_AGENT,
    }, method="POST")
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw, http_status = response.read(), getattr(response, "status", 200)
    except HTTPError as exc:
        diagnostics = {"provider_http_status": exc.code}
        try:
            error_body = exc.read(4096).decode("utf-8", errors="replace")
        except OSError as read_error:
            error_body = ""
            diagnostics["provider_error_body_read_failure"] = type(read_error).__name__
        if api_key:
            error_body = error_body.replace(api_key, "[REDACTED]")
        diagnostics["provider_error_body"] = error_body
        try:
            parsed_error = json.loads(error_body)
        except json.JSONDecodeError:
            parsed_error = None
        if isinstance(parsed_error, dict):
            diagnostics["provider_error_json"] = parsed_error
        headers = exc.headers or {}
        if headers.get("Content-Type"):
            diagnostics["provider_content_type"] = headers["Content-Type"]
        request_id = headers.get("x-request-id") or headers.get("request-id")
        if request_id:
            diagnostics["provider_request_id"] = request_id
        return None, f"HTTP_{exc.code}", diagnostics
    except (URLError, TimeoutError, OSError) as exc:
        return None, type(exc).__name__, None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "INVALID_PROVIDER_JSON", {"provider_http_status": http_status}
    if not isinstance(decoded, dict):
        return None, "INVALID_PROVIDER_RESPONSE", {"provider_http_status": http_status}
    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None, "MISSING_COMPLETION", {"provider_http_status": http_status}
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return None, "MISSING_COMPLETION_CONTENT", {"provider_http_status": http_status}
    return {
        "content": content, "provider_response_id": decoded.get("id"),
        "provider_model_id": decoded.get("model"), "http_status": http_status,
    }, None, None

def _call_groq(*, api_key, endpoint, model_id, prompt, max_tokens):
    return _call_openai_compatible(
        api_key=api_key,
        endpoint=endpoint,
        model_id=model_id,
        prompt=prompt,
        max_tokens=max_tokens,
    )

def _call_anymodel(*, api_key, endpoint, model_id, prompt, max_tokens):
    return _call_openai_compatible(
        api_key=api_key,
        endpoint=endpoint,
        model_id=model_id,
        prompt=prompt,
        max_tokens=max_tokens,
    )

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=Path("prompts.json"))
    parser.add_argument("--responses", type=Path, default=Path("llm_responses_v3.json"))
    parser.add_argument("--manifest", type=Path, default=Path("generation_manifest.json"))
    parser.add_argument("--provider", choices=("groq", "anymodel"), default="groq")
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    provider = args.provider
    key_name = "ANYMODEL_API_KEY" if provider == "anymodel" else "GROQ_API_KEY"
    model_env = "ANYMODEL_MODEL" if provider == "anymodel" else "GROQ_MODEL"
    api_key = os.environ.get(key_name, "")
    model_id = (args.model or os.environ.get(model_env, "")).strip()
    base_env = "ANYMODEL_BASE_URL" if provider == "anymodel" else "GROQ_BASE_URL"
    base_url = (args.base_url or os.environ.get(base_env, PROVIDER_DEFAULTS[provider])).rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    max_tokens = int(os.environ.get("GROQ_MAX_TOKENS", "1024"))
    parsed = urlparse(base_url)
    if not api_key:
        raise SystemExit(f"{key_name} is required")
    if not model_id:
        raise SystemExit(f"--model or {model_env} is required; model identity must be pinned")
    if not 1 <= args.limit <= 100:
        raise SystemExit("--limit must be between 1 and 100")
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SystemExit("provider base URL must be HTTPS and contain no credentials/query")
    if max_tokens <= 0:
        raise SystemExit("GROQ_MAX_TOKENS must be positive")

    prompts, raw_prompts = _read_prompts(args.prompts)
    samples = prompts["samples"][:args.limit]
    prompt_hash = hashlib.sha256(raw_prompts).hexdigest()
    started_at = datetime.now(UTC).isoformat()
    results, provider_model_ids = [], set()
    call = _call_groq if provider == "groq" else _call_anymodel
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("each prompt row must be a JSON object")
        sample_id = sample.get("sample_id")
        prompt = sample.get("prompt")
        package_name = sample.get("package_name")
        if not all(isinstance(value, str) and value for value in (sample_id, prompt, package_name)):
            raise ValueError("each prompt requires sample_id, package_name, and prompt")
        timestamp = datetime.now(UTC).isoformat()
        response, failure, provider_error = call(
            api_key=api_key,
            endpoint=endpoint,
            model_id=model_id,
            prompt=prompt,
            max_tokens=max_tokens,
        )
        if failure or response is None:
            row = {
                "sample_id": sample_id, "package_name": package_name, "prompt": prompt,
                "request_status": "FAILED", "failure_reason": failure or "unknown_provider_failure",
                "request_timestamp_utc": timestamp,
                "http_status": (
                    provider_error.get("provider_http_status") if provider_error else None
                ),
            }
            if provider_error is not None:
                row["provider_error"] = provider_error
            results.append(row)
            continue
        returned_model, content = response.get("provider_model_id"), response.get("content")
        if isinstance(returned_model, str) and returned_model:
            provider_model_ids.add(returned_model)
        package, code = _parse_completion(content) if isinstance(content, str) else (None, None)
        status, reason = "SUCCESS", None
        if package != package_name or code is None:
            status, reason = "MALFORMED_RESPONSE", "completion_not_valid_expected_json"
        elif not code.strip():
            status, reason = "ABSTAINED", None
        if returned_model != model_id:
            status = "MODEL_ID_MISMATCH"
            reason = "provider_returned_model_differs_from_requested_model"
        if response.get("http_status") != 200:
            status, reason = "HTTP_STATUS_NOT_200", "provider_http_status_must_be_200"
        results.append({
            "sample_id": sample_id, "package_name": package_name, "prompt": prompt,
            "request_status": status, "failure_reason": reason, "request_timestamp_utc": timestamp,
            "http_status": response.get("http_status"),
            "provider_response_id": response.get("provider_response_id"),
            "provider_model_id": returned_model, "content": content, "code": code,
        })

    payload = {
        "schema_version": "jamp-hunt-llm-responses-v0.3",
        "evidence_class": "LIVE_LLM_GENERATIONS",
        "provider_name": provider,
        "samples": results,
    }
    args.responses.parent.mkdir(parents=True, exist_ok=True)
    response_bytes = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    args.responses.write_bytes(response_bytes)
    response_hash = hashlib.sha256(response_bytes).hexdigest()
    successful = sum(row["request_status"] == "SUCCESS" for row in results)
    abstained = sum(row["request_status"] == "ABSTAINED" for row in results)
    failed = len(results) - successful - abstained
    manifest = {
        "schema_version": "jamp-hunt-generation-manifest-v0.3",
        "experiment_id": f"hunt-v03-{started_at}",
        "evaluation_mode": "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY", "provider_name": provider,
        "provider_base_url": base_url,
        "provider_endpoint": endpoint,
        "requested_model_id": model_id,
        "provider_model_id": (
            next(iter(provider_model_ids)) if len(provider_model_ids) == 1 else None
        ),
        "provider_model_ids_observed": sorted(provider_model_ids), "temperature": TEMPERATURE,
        "max_completion_tokens": max_tokens, "prompt_dataset_sha256": prompt_hash,
        "generation_timestamp_utc": started_at,
        "completion_timestamp_utc": datetime.now(UTC).isoformat(),
        "successful_requests": successful, "abstained_requests": abstained,
        "failed_requests": failed,
        "request_count": len(results), "llm_responses_sha256": response_hash,
        "llm_responses_file": args.responses.name,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.limit == 1:
        row = results[0]
        control = {
            "schema_version": "jamp-hunt-control-response-v0.3", "provider_name": provider,
            "requested_model_id": model_id, "provider_model_id": row.get("provider_model_id"),
            "http_status": row.get("http_status"), "request_status": row.get("request_status"),
            "failure_reason": row.get("failure_reason"), "content": row.get("content"),
            "content_sha256": hashlib.sha256(str(row.get("content") or "").encode()).hexdigest(),
            "response_file_sha256": response_hash, "qualification": "NOT_GRANTED",
        }
        (args.manifest.parent / "control_response.json").write_text(
            json.dumps(control, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"provider": provider, "requested_model_id": model_id,
        "provider_model_id": manifest["provider_model_id"], "temperature": TEMPERATURE,
        "request_count": len(results), "successful_requests": successful,
        "abstained_requests": abstained, "failed_requests": failed,
        "limit": args.limit}, sort_keys=True))
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
