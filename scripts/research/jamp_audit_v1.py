#!/usr/bin/env python3
"""Fail-closed, evidence-preserving JAMP Audit v1 runner.

The default command is help/verification. Paid chat requests are possible only
through the explicit `execute` subcommand; catalog preflight is GET-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
INPUT_PACK_PATH = ROOT / "docs/experiments/jamp_audit_v1/INPUT_PACK.md"
COST_BASELINE_PATH = ROOT / "docs/experiments/jamp_audit_v1/COST_BASELINE.md"
OUTPUT_ROOT = ROOT / "artifacts/research/jamp_audit_v1"
BASE_URL = os.getenv("ANYMODEL_BASE_URL", "https://anymodel.org").rstrip("/")
CATALOG_URL = f"{BASE_URL}/v1/models"
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
MAX_MODELS = 100
MAX_MODELS_FIRST_RUN = 3
MODEL_KEY_RE = re.compile(r"^[a-z0-9_]{3,32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
KNOWN_FINISH_REASONS = {"stop", "length", "content_filter"}

MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "model_001": {"provider": "anymodel", "model_id": "ag/claude-sonnet-4-6",
                  "enabled": True, "request_params": {"max_tokens": 4096, "temperature": 0}},
    "model_002": {"provider": "anymodel", "model_id": "ag/gemini-3.8-flash-high",
                  "enabled": True, "request_params": {"max_tokens": 4096, "temperature": 0}},
    "model_003": {"provider": "anymodel", "model_id": "kmc/kimi-for-coding",
                  "enabled": True, "request_params": {"max_tokens": 4096, "temperature": 0}},
}

AUDIT_PROMPT = """# JAMP Independent Audit v1

Ты — независимый технический аудитор. Анализируй только предоставленный INPUT PACK.
Не добавляй внешние факты и не превращай предположения в доказательства.

Для каждого существенного утверждения укажи уровень: VERIFIED (только в пределах
приведённого evidence), OBSERVED, INFERRED или UNKNOWN/NEED INFO. Учитывай, что
у тебя нет доступа к первичным GitHub Runs, Jobs, Artifacts и исходникам: ссылки
не означают, что их содержимое независимо проверено. Совпадение выводов нескольких
моделей не является доказательством истины.

Подготовь:
1. Краткую карту реально подтверждённых возможностей и их границ.
2. Реализованные/наблюдаемые компоненты, для которых production-эффект неизвестен.
3. Gaps: отдельно блокирующие безопасный продуктовый запуск и не блокирующие
   исследовательскую работу; обоснуй каждую классификацию.
4. Приоритетный план следующих действий. Для каждого действия дай цель,
   конкретный Definition of Done и требуемое первичное evidence.
5. NEED INFO: точный источник/артефакт, который нужен для разрешения неопределённости.

Не объявляй продукт готовым, модели квалифицированными, Tenant Isolation
подтверждённым или Stage C закрытым. Не делай вывод о коммерческом спросе.
Заверши общим вердиктом: READY_FOR_NEXT_RESEARCH_STEP, HOLD или REFUSE,
объяснив границы этого вердикта. Это не оценка коммерческой готовности.
"""

class FinalStatus(StrEnum):
    COMPLETED = "COMPLETED"
    EMPTY = "EMPTY"
    TRUNCATED = "TRUNCATED"
    CONTENT_FILTERED = "CONTENT_FILTERED"
    API_ERROR = "API_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    EXCEPTION = "EXCEPTION"

COMPARABLE_STATUSES = {FinalStatus.COMPLETED}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_uuid(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4 and str(parsed) == value


def validate_registry(registry: dict[str, dict[str, Any]] = MODEL_REGISTRY) -> None:
    if len(registry) > MAX_MODELS:
        raise ValueError("Registry exceeds MAX_MODELS")
    seen: set[str] = set()
    for key, item in registry.items():
        if not isinstance(key, str) or not MODEL_KEY_RE.fullmatch(key):
            raise ValueError(f"Invalid model key: {key!r}")
        if key in seen:
            raise ValueError(f"Duplicate model key: {key}")
        seen.add(key)
        if not isinstance(item, dict) or item.get("provider") != "anymodel":
            raise NotImplementedError("Only the AnyModel provider is implemented")
        model_id = item.get("model_id")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"Invalid model_id for {key}")
        params = item.get("request_params")
        if not isinstance(params, dict) or set(params) - {"max_tokens", "temperature"}:
            raise ValueError(f"Invalid request parameter allowlist for {key}")
        tokens = params.get("max_tokens")
        temp = params.get("temperature")
        if isinstance(tokens, bool) or not isinstance(tokens, int) or not 1 <= tokens <= 8192:
            raise ValueError(f"Invalid max_tokens for {key}")
        if isinstance(temp, bool) or not isinstance(temp, (int, float)) or not 0 <= temp <= 2:
            raise ValueError(f"Invalid temperature for {key}")
        if not isinstance(item.get("enabled"), bool):
            raise ValueError(f"Invalid enabled flag for {key}")
    ids = [v["model_id"] for v in registry.values()]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate model_id in registry")


def select_models(value: str) -> list[str]:
    validate_registry()
    if value == "all":
        selected = [k for k, v in MODEL_REGISTRY.items() if v["enabled"]]
    else:
        selected = value.split(",")
        if not selected or any(not MODEL_KEY_RE.fullmatch(k) for k in selected):
            raise ValueError("Malformed model selection")
        if len(selected) != len(set(selected)):
            raise ValueError("Duplicate model selection")
        if any(k not in MODEL_REGISTRY for k in selected):
            raise ValueError("Unknown model key")
        if any(not MODEL_REGISTRY[k]["enabled"] for k in selected):
            raise ValueError("Disabled model selected")
    if not selected or len(selected) > MAX_MODELS:
        raise ValueError("Invalid model selection size")
    return selected


def classify_response(http_status: int, body: Any) -> FinalStatus:
    if http_status != 200:
        return FinalStatus.API_ERROR
    if not isinstance(body, dict):
        return FinalStatus.INVALID_RESPONSE
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return FinalStatus.INVALID_RESPONSE
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict) or "content" not in message:
        return FinalStatus.INVALID_RESPONSE
    finish = choice.get("finish_reason")
    if not isinstance(finish, str) or finish not in KNOWN_FINISH_REASONS:
        return FinalStatus.INVALID_RESPONSE
    if finish == "content_filter":
        return FinalStatus.CONTENT_FILTERED
    content = message["content"]
    if content is not None and not isinstance(content, str):
        return FinalStatus.INVALID_RESPONSE
    if finish == "length":
        if isinstance(content, str) and content:
            return FinalStatus.TRUNCATED
        return FinalStatus.EMPTY
    if content is None or content == "":
        return FinalStatus.EMPTY
    if not content.strip():
        return FinalStatus.INVALID_RESPONSE
    return FinalStatus.COMPLETED


def read_input_pack() -> str:
    raw = INPUT_PACK_PATH.read_bytes()
    return raw.decode("utf-8")


def composite_prompt() -> str:
    return AUDIT_PROMPT + "\n\n### INPUT PACK\n" + read_input_pack()


def emit_snapshots(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    input_raw = INPUT_PACK_PATH.read_bytes()
    audit_hash = sha256(AUDIT_PROMPT.encode("utf-8"))
    input_hash = sha256(input_raw)
    composite_hash = sha256((AUDIT_PROMPT + "\n\n### INPUT PACK\n" +
                             input_raw.decode("utf-8")).encode("utf-8"))
    values = {
        "audit_spec_v1.sha256": audit_hash,
        "input_pack_v1.sha256": input_hash,
        "prompt_composite_v1.sha256": composite_hash,
    }
    for name, digest in values.items():
        (directory / name).write_text(digest + "\n", encoding="ascii")


def verify_snapshots(directory: Path) -> None:
    expected = {
        "audit_spec_v1.sha256": sha256(AUDIT_PROMPT.encode("utf-8")),
        "input_pack_v1.sha256": sha256(INPUT_PACK_PATH.read_bytes()),
        "prompt_composite_v1.sha256": sha256(composite_prompt().encode("utf-8")),
    }
    for name, digest in expected.items():
        path = directory / name
        if not path.is_file():
            raise ValueError(f"Missing snapshot: {name}")
        actual = path.read_text(encoding="ascii").strip()
        if not SHA256_RE.fullmatch(actual) or actual != digest:
            raise ValueError(f"Snapshot mismatch: {name}")


def is_first_run(cost_path: Path = COST_BASELINE_PATH) -> bool:
    """Fail closed unless a complete manifest→usage→metadata chain is recorded."""
    try:
        text = cost_path.read_text(encoding="utf-8")
        blocks = re.split(r"(?m)^### model: ", text)[1:]
        valid = 0
        seen_model_ids: set[str] = set()
        for block in blocks:
            lines = block.splitlines()
            if not lines:
                return True
            model_id = lines[0].strip()
            if not model_id or model_id in seen_model_ids:
                return True
            seen_model_ids.add(model_id)
            fields: dict[str, str] = {}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()
            prompt_tokens = int(fields["usage.prompt_tokens"])
            completion_tokens = int(fields["usage.completion_tokens"])
            run_id, artifact_id = fields["source_run_id"], fields["source_artifact_id"]
            manifest_file, metadata_file = fields["manifest_file"], fields["metadata_file"]
            if (not model_id or prompt_tokens <= 0 or completion_tokens < 0
                    or not run_id.isdigit() or not artifact_id.isdigit()):
                return True
            if Path(manifest_file).is_absolute() or ".." in Path(manifest_file).parts:
                return True
            if Path(metadata_file).is_absolute() or ".." in Path(metadata_file).parts:
                return True
            manifest = json.loads((ROOT / manifest_file).read_text(encoding="utf-8"))
            metadata = json.loads((ROOT / metadata_file).read_text(encoding="utf-8"))
            model_key = metadata.get("model_key")
            metadata_files = manifest.get("metadata_files")
            manifest_usage = manifest.get("usage")
            usage = metadata.get("usage")
            enabled_models = manifest.get("enabled_models")
            available_models = manifest.get("available_models")
            executed_models = manifest.get("executed_models")
            completed_models = manifest.get("completed_models")
            if (
                    not isinstance(enabled_models, list)
                    or len(enabled_models) > MAX_MODELS_FIRST_RUN
                    or len(enabled_models) != len(set(enabled_models))
                    or available_models != enabled_models
                    or executed_models != available_models
                    or completed_models != executed_models
                    or manifest.get("skipped_models") != []
                    or manifest.get("failed_models") != []
                    or not isinstance(manifest_usage, dict)
                    or manifest_usage.get(model_key) != usage
                    or not isinstance(metadata_files, dict)
                    or metadata_files.get(model_key) != metadata_file
                    or manifest.get("status") != "COMPLETED"
                    or model_key not in manifest.get("completed_models", [])
                    or model_key not in manifest.get("executed_models", [])
                    or metadata.get("status") != FinalStatus.COMPLETED.value
                    or metadata.get("experiment_id") != manifest.get("experiment_id")
                    or metadata.get("model_id") != model_id
                    or not isinstance(manifest.get("repository_commit_sha"), str)
                    or not GIT_SHA_RE.fullmatch(manifest["repository_commit_sha"])
                    or metadata.get("repository_commit_sha") != manifest["repository_commit_sha"]
                    or metadata.get("source_run_id") != run_id
                    or metadata.get("source_artifact_id") != artifact_id
                    or not isinstance(usage, dict)
                    or isinstance(usage.get("prompt_tokens"), bool)
                    or not isinstance(usage.get("prompt_tokens"), int)
                    or isinstance(usage.get("completion_tokens"), bool)
                    or not isinstance(usage.get("completion_tokens"), int)
                    or usage.get("prompt_tokens") != prompt_tokens
                    or usage.get("completion_tokens") != completion_tokens):
                return True
            valid += 1
        return valid == 0 or valid > MAX_MODELS_FIRST_RUN
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return True


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, new_url: str
    ) -> None:
        return None


def http_get_catalog(api_key: str) -> bytes:
    request = urllib.request.Request(CATALOG_URL, headers={
        "Authorization": f"Bearer {api_key}", "Accept": "application/json",
        "User-Agent": "JAMP-Audit-v1",
    })
    try:
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"Catalog HTTP {response.status}")
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Catalog HTTP {exc.code}") from exc
    json.loads(raw.decode("utf-8"))
    return raw


def catalog_ids(raw: bytes) -> set[str]:
    data = json.loads(raw.decode("utf-8"))
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Catalog schema missing data list")
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]:
            raise ValueError("Catalog contains a malformed model entry")
        ids.append(row["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("Catalog contains duplicate model IDs")
    return set(ids)


def git_commit_sha() -> str:
    value = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not GIT_SHA_RE.fullmatch(value):
        raise ValueError("Cannot establish repository commit SHA")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def preflight(models: list[str], experiment_id: str, output_dir: Path) -> str:
    if not canonical_uuid(experiment_id):
        raise ValueError("experiment_id must be canonical lowercase UUIDv4")
    if len(models) > MAX_MODELS_FIRST_RUN and is_first_run():
        raise ValueError("First run is limited to MAX_MODELS_FIRST_RUN=3")
    key = os.getenv("ANYMODEL_API_KEY")
    if not key:
        raise RuntimeError("ANYMODEL_API_KEY is required for catalog preflight")
    raw = http_get_catalog(key)
    digest = sha256(raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = output_dir / "catalog_snapshot.json"
    if snapshot.exists():
        raise FileExistsError(f"Refusing to overwrite catalog snapshot: {snapshot}")
    snapshot.write_bytes(raw)
    ids = catalog_ids(raw)
    available = sorted(
        key for key in models if MODEL_REGISTRY[key]["model_id"] in ids
    )
    result = {"experiment_id": experiment_id, "catalog_sha256": digest,
              "catalog_bytes": len(raw), "selected_model_keys": models,
              "available_model_keys": available,
              "unavailable_model_keys": sorted(set(models) - set(available)),
              "repository_commit_sha": git_commit_sha()}
    atomic_json(output_dir / "preflight.json", result)
    return digest


def validate_manifest(manifest: dict[str, Any], output_dir: Path) -> None:
    def string_list(name: str) -> list[str]:
        value = manifest.get(name)
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            raise ValueError(f"{name} must be a list of strings")
        if len(value) != len(set(value)):
            raise ValueError(f"{name} contains duplicates")
        return value

    enabled = set(string_list("enabled_models"))
    available = set(string_list("available_models"))
    if not enabled <= set(MODEL_REGISTRY):
        raise ValueError("Manifest contains unknown enabled model keys")
    def record_keys(name: str, require_status: bool) -> dict[str, dict[str, str]]:
        records = manifest.get(name)
        if not isinstance(records, list):
            raise ValueError(f"{name} must be a list of objects")
        parsed: dict[str, dict[str, str]] = {}
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"{name} entries must be objects")
            key, reason = record.get("key"), record.get("reason")
            if (
                not isinstance(key, str)
                or not key
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                raise ValueError(f"Invalid {name} entry")
            if key in parsed:
                raise ValueError(f"Duplicate key in {name}")
            if require_status:
                status = record.get("status")
                if not isinstance(status, str):
                    raise ValueError("Failed entry requires a status")
                try:
                    parsed[key] = {"reason": reason, "status": FinalStatus(status).value}
                except ValueError as exc:
                    raise ValueError("Unknown failed model status") from exc
                if parsed[key]["status"] == FinalStatus.COMPLETED.value:
                    raise ValueError("Failed model cannot be COMPLETED")
            else:
                parsed[key] = {"reason": reason}
        return parsed

    skipped_records = record_keys("skipped_models", False)
    failed_records = record_keys("failed_models", True)
    skipped, failed = set(skipped_records), set(failed_records)
    executed = set(string_list("executed_models"))
    completed = set(string_list("completed_models"))
    still_running = string_list("still_running")
    if not available <= enabled or skipped != enabled - available:
        raise ValueError("available/skipped invariant violated")
    if not executed <= available or not completed <= executed:
        raise ValueError("executed/completed invariant violated")
    if failed != executed - completed or still_running:
        raise ValueError("terminal batch invariant violated")
    expected_hashes = {
        "audit_spec_sha256": sha256(AUDIT_PROMPT.encode("utf-8")),
        "input_pack_sha256": sha256(INPUT_PACK_PATH.read_bytes()),
        "prompt_sha256": sha256(composite_prompt().encode("utf-8")),
    }
    for name, expected in expected_hashes.items():
        value = manifest.get(name)
        if not isinstance(value, str) or not SHA256_RE.fullmatch(value) or value != expected:
            raise ValueError(f"Invalid or unexpected {name}")
    commit = manifest.get("repository_commit_sha")
    if (
        not isinstance(commit, str)
        or not GIT_SHA_RE.fullmatch(commit)
        or commit != git_commit_sha()
    ):
        raise ValueError("Invalid or unexpected repository_commit_sha")
    if not canonical_uuid(manifest.get("experiment_id")):
        raise ValueError("Invalid experiment_id")
    metadata_files = manifest.get("metadata_files")
    response_files = manifest.get("response_files")
    if not isinstance(metadata_files, dict) or set(metadata_files) != executed:
        raise ValueError("Metadata files must correspond exactly to executed models")
    if not isinstance(response_files, dict) or set(response_files) != completed:
        raise ValueError("Response files must correspond exactly to completed models")
    expected_metadata_names = {f"{key}.metadata.json" for key in executed}
    expected_response_names = {f"{key}.md" for key in completed}
    if {p.name for p in output_dir.glob("*.metadata.json")} != expected_metadata_names:
        raise ValueError("Unexpected or missing metadata files")
    if {p.name for p in output_dir.glob("*.md")} != expected_response_names:
        raise ValueError("Unexpected or missing response files")
    manifest_status = manifest.get("status")
    if not isinstance(manifest_status, str) or manifest_status not in {"COMPLETED", "PARTIAL"}:
        raise ValueError("Manifest is not terminal")
    expected_status = "COMPLETED" if not failed and not skipped else "PARTIAL"
    if manifest_status != expected_status:
        raise ValueError("Manifest terminal status is inconsistent")
    for key in executed:
        metadata_name = metadata_files[key]
        if not isinstance(metadata_name, str) or metadata_name != f"{key}.metadata.json":
            raise ValueError("Invalid metadata filename")
        metadata_path = output_dir / metadata_name
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("Metadata document must be an object")
        status = metadata.get("status")
        if not isinstance(status, str):
            raise ValueError("Metadata status must be a string")
        try:
            enum_status = FinalStatus(status)
        except ValueError as exc:
            raise ValueError("Unknown metadata status") from exc
        if (
            metadata.get("model_key") != key
            or metadata.get("provider") != MODEL_REGISTRY[key]["provider"]
            or metadata.get("model_id") != MODEL_REGISTRY[key]["model_id"]
            or metadata.get("experiment_id") != manifest["experiment_id"]
        ):
            raise ValueError("Metadata identity mismatch")
        for field in ("audit_spec_sha256", "input_pack_sha256", "prompt_sha256"):
            if metadata.get(field) != manifest[field]:
                raise ValueError(f"Metadata {field} mismatch")
        if metadata.get("repository_commit_sha") != commit:
            raise ValueError("Metadata repository commit mismatch")
        usage_records = manifest.get("usage")
        metadata_usage = metadata.get("usage")
        if (
            not isinstance(usage_records, dict)
            or set(usage_records) - executed
            or any(not isinstance(value, dict) for value in usage_records.values())
        ):
            raise ValueError("Manifest usage records must map executed models only")
        if metadata_usage is None:
            if key in usage_records:
                raise ValueError("Manifest/metadata usage mismatch")
        elif not isinstance(metadata_usage, dict) or usage_records.get(key) != metadata_usage:
            raise ValueError("Manifest/metadata usage mismatch")
        if (key in completed) != (enum_status == FinalStatus.COMPLETED):
            raise ValueError("Metadata status/completed set mismatch")
        if key in failed:
            if enum_status.value != failed_records[key]["status"]:
                raise ValueError("Failed manifest/metadata status mismatch")
            if metadata.get("reason") and metadata["reason"] != failed_records[key]["reason"]:
                raise ValueError("Failed manifest/metadata reason mismatch")
    for key in completed:
        response_name = response_files[key]
        if not isinstance(response_name, str) or response_name != f"{key}.md":
            raise ValueError("Invalid response filename")
        path = output_dir / response_name
        raw = path.read_bytes()
        if not raw:
            raise ValueError("Completed response file is empty")
        metadata = json.loads((output_dir / metadata_files[key]).read_text(encoding="utf-8"))
        if sha256(raw) != metadata.get("response_sha256"):
            raise ValueError("Response checksum mismatch")


def execute(models: list[str], experiment_id: str, snapshot_path: Path,
            expected_catalog_sha: str, inter_request_seconds: int, output_dir: Path) -> None:
    if not canonical_uuid(experiment_id):
        raise ValueError("experiment_id must be canonical lowercase UUIDv4")
    if (
        isinstance(inter_request_seconds, bool)
        or not isinstance(inter_request_seconds, int)
        or not 0 <= inter_request_seconds <= 600
    ):
        raise ValueError("inter_request_seconds must be an integer in 0..600")
    if not SHA256_RE.fullmatch(expected_catalog_sha):
        raise ValueError("Invalid expected catalog SHA-256")
    raw_catalog = snapshot_path.read_bytes()
    if sha256(raw_catalog) != expected_catalog_sha:
        raise ValueError("Catalog snapshot integrity mismatch; refusing paid requests")
    available_ids = catalog_ids(raw_catalog)
    selected = select_models(",".join(models))
    if len(selected) > MAX_MODELS_FIRST_RUN and is_first_run():
        raise ValueError("First run limit exceeded")
    if (
        snapshot_path.name != "catalog_snapshot.json"
        or snapshot_path.parent.resolve() != output_dir.resolve()
    ):
        raise ValueError("Catalog snapshot must belong to this experiment output directory")
    preflight_path = output_dir / "preflight.json"
    preflight_record = json.loads(preflight_path.read_text(encoding="utf-8"))
    commit = git_commit_sha()
    expected_available = sorted(
        key for key in selected if MODEL_REGISTRY[key]["model_id"] in available_ids
    )
    if (
        preflight_record.get("experiment_id") != experiment_id
        or preflight_record.get("catalog_sha256") != expected_catalog_sha
        or preflight_record.get("selected_model_keys") != selected
        or preflight_record.get("available_model_keys") != expected_available
        or preflight_record.get("repository_commit_sha") != commit
    ):
        raise ValueError("Preflight record does not match this execution request")
    api_key = os.getenv("ANYMODEL_API_KEY")
    if not api_key:
        raise RuntimeError("ANYMODEL_API_KEY is required")
    if output_dir.exists() and (
        (output_dir / "manifest.json").exists()
        or list(output_dir.glob("*.metadata.json"))
        or list(output_dir.glob("model_*.md"))
    ):
        raise FileExistsError("Experiment output already exists; refusing overwrite")
    prompt = composite_prompt()
    audit_hash = sha256(AUDIT_PROMPT.encode("utf-8"))
    input_hash = sha256(INPUT_PACK_PATH.read_bytes())
    prompt_hash = sha256(prompt.encode("utf-8"))
    enabled = list(selected)
    available = [k for k in selected if MODEL_REGISTRY[k]["model_id"] in available_ids]
    skipped = [{"key": k, "reason": "MODEL_NOT_IN_CATALOG"} for k in selected if k not in available]
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema_version": "1.0", "experiment_id": experiment_id,
        "repository_commit_sha": commit, "audit_spec_sha256": audit_hash,
        "input_pack_sha256": input_hash, "prompt_sha256": prompt_hash,
        "enabled_models": enabled, "available_models": available,
        "skipped_models": skipped, "executed_models": [],
        "completed_models": [], "failed_models": [], "still_running": [],
        "metadata_files": {}, "response_files": {}, "usage": {},
    }
    atomic_json(output_dir / "manifest.json", manifest)
    for index, key in enumerate(available):
        item = MODEL_REGISTRY[key]
        payload = {"model": item["model_id"],
                   "messages": [{"role": "user", "content": prompt}],
                   **item["request_params"]}
        status = FinalStatus.EXCEPTION
        content_raw = b""
        usage: dict[str, Any] | None = None
        reason = ""
        try:
            request = urllib.request.Request(CHAT_URL, data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                         "Accept": "application/json", "User-Agent": "JAMP-Audit-v1"})
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(request, timeout=240) as response:
                http_status = response.status
                response_raw = response.read()
            body = json.loads(response_raw.decode("utf-8"))
            status = classify_response(http_status, body)
            if isinstance(body, dict) and isinstance(body.get("usage"), dict):
                usage = body["usage"]
            if status in COMPARABLE_STATUSES:
                content_raw = body["choices"][0]["message"]["content"].encode("utf-8")
            else:
                reason = f"Response classified as {status.value}"
        except urllib.error.HTTPError as exc:
            status, reason = FinalStatus.API_ERROR, f"HTTP {exc.code}"
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            status, reason = FinalStatus.INVALID_RESPONSE, f"{type(exc).__name__}: {exc}"
        except OSError as exc:
            status, reason = FinalStatus.EXCEPTION, f"{type(exc).__name__}: {exc}"
        manifest["executed_models"].append(key)
        if usage is not None:
            manifest["usage"][key] = usage
        metadata_name = f"{key}.metadata.json"
        metadata = {"model_key": key, "provider": item["provider"], "model_id": item["model_id"],
                    "experiment_id": experiment_id, "repository_commit_sha": commit,
                    "audit_spec_sha256": audit_hash, "input_pack_sha256": input_hash,
                    "prompt_sha256": prompt_hash, "status": status.value,
                    "usage": usage, "reason": reason or None}
        if status == FinalStatus.COMPLETED:
            response_name = f"{key}.md"
            (output_dir / response_name).write_bytes(content_raw)
            metadata["response_sha256"] = sha256(content_raw)
            manifest["completed_models"].append(key)
            manifest["response_files"][key] = response_name
        else:
            manifest["failed_models"].append({
                "key": key, "reason": reason or status.value, "status": status.value
            })
        atomic_json(output_dir / metadata_name, metadata)
        manifest["metadata_files"][key] = metadata_name
        atomic_json(output_dir / "manifest.json", manifest)
        if index + 1 < len(available) and inter_request_seconds:
            time.sleep(inter_request_seconds)
    manifest["status"] = "COMPLETED" if not manifest["failed_models"] and not skipped else "PARTIAL"
    atomic_json(output_dir / "manifest.json", manifest)
    validate_manifest(manifest, output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-snapshots", type=Path)
    parser.add_argument("--verify-snapshots", type=Path)
    sub = parser.add_subparsers(dest="command")
    pre = sub.add_parser("preflight")
    pre.add_argument("--models", default="all")
    pre.add_argument("--experiment-id", required=True)
    pre.add_argument("--output-dir", type=Path)
    run = sub.add_parser("execute")
    run.add_argument("--models", default="all")
    run.add_argument("--experiment-id", required=True)
    run.add_argument("--catalog-snapshot", type=Path, required=True)
    run.add_argument("--expected-catalog-sha", required=True)
    run.add_argument("--inter-request-seconds", type=int, default=0)
    run.add_argument("--output-dir", type=Path)
    check = sub.add_parser("verify")
    check.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.emit_snapshots:
            emit_snapshots(args.emit_snapshots)
            return 0
        if args.verify_snapshots:
            verify_snapshots(args.verify_snapshots)
            return 0
        if args.command == "preflight":
            output_dir = args.output_dir or OUTPUT_ROOT / args.experiment_id
            digest = preflight(
                select_models(args.models), args.experiment_id, output_dir
            )
            print(json.dumps({"catalog_sha256": digest}, indent=2))
            return 0
        if args.command == "execute":
            output_dir = args.output_dir or OUTPUT_ROOT / args.experiment_id
            execute(
                select_models(args.models),
                args.experiment_id,
                args.catalog_snapshot,
                args.expected_catalog_sha,
                args.inter_request_seconds,
                output_dir,
            )
            return 0
        if args.command == "verify":
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            validate_manifest(manifest, args.manifest.parent)
            return 0
        parser.print_help()
        return 0
    except Exception as exc:
        print(f"REFUSE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
