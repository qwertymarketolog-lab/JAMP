"""Recover independent API Ground Truth from immutable DeepSeek v0.3 evidence.

The original package-existence labels and generated responses are immutable.
Only AST-derived imports/attributes/callability are probed in isolated,
network-disabled per-sample environments. This does not validate signatures
or behavioral compatibility.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import resource
import subprocess
import sys
import tempfile
import time
import venv
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

ARTIFACT_ID = 13347295508
ARTIFACT_SHA256 = "576c570f0d960719ccf68f16a632f373352e066e3c12f0474978659ebeeb08b5"
ARTIFACT_SIZE = 97441836
PROVIDER_NAME = "anymodel"
MODEL_ID = "ds/deepseek-v4-pro"
EXPECTED_STATUS_COUNTS = {"SUCCESS": 21, "ABSTAINED": 77, "MALFORMED_RESPONSE": 2}
EXPECTED_FILES = {
    "generation_manifest.json": "5bc6f99a9b85f2647a9d8ff3e2ec9de637454c1b303b6c2bf1a7018e4d438461",
    "llm_responses_v3.json": "b3cf8160e4a622c14c946e77079d30fdc9ec34692c8f7fb8b2c4122dcdcc054b",
    "ground_truth_v3.json": "06af6391f23bb4afd5ac8667f8f501f4e034e822d7c5f2b271901a4d69cff01a",
    "prompts.json": "7d9721ac6ce6d2235d42a447971e31f5143fe50d246549673253309de927c9d8",
    "generation_snapshot.json": "9eabd6b28a62ac84722f0d3e3b36c7aca0c389c22d967cca79ce31f9ccb57458",
}
PROBE_SOURCE = r'''import importlib, json, sys
probes = json.loads(sys.argv[1])
missing = []
for probe in probes:
    module_name = probe["module"]
    try:
        current = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or module_name.startswith(str(exc.name) + "."):
            missing.append({"probe": probe, "kind": "missing_module", "error": str(exc)[:500]})
            continue
        print(json.dumps({"api_valid": None, "reason": "dependency_import_failed",
                          "error": str(exc)[:500]}))
        raise SystemExit(0)
    except Exception as exc:
        print(json.dumps({"api_valid": None, "reason": "module_import_failed",
                          "error_type": type(exc).__name__, "error": str(exc)[:500]}))
        raise SystemExit(0)
    try:
        for part in probe.get("attributes", []):
            try:
                current = getattr(current, part)
            except AttributeError:
                try:
                    current = importlib.import_module(module_name + "." + part)
                except ModuleNotFoundError as exc:
                    expected = module_name + "." + part
                    if exc.name == expected or expected.startswith(str(exc.name) + "."):
                        missing.append({"probe": probe, "kind": "missing_attribute_or_submodule"})
                        break
                    raise
        if probe.get("callable") and not callable(current):
            missing.append({"probe": probe, "kind": "symbol_not_callable"})
    except AttributeError as exc:
        missing.append({"probe": probe, "kind": "missing_attribute", "error": str(exc)[:500]})
    except Exception as exc:
        print(json.dumps({"api_valid": None, "reason": "attribute_resolution_failed",
                          "error_type": type(exc).__name__, "error": str(exc)[:500]}))
        raise SystemExit(0)
print(json.dumps({"api_valid": False, "reason": "api_symbol_missing", "missing": missing},
                 sort_keys=True) if missing else
      json.dumps({"api_valid": True, "reason": "all_static_imports_and_attributes_resolved"},
                 sort_keys=True))
'''


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_hash(payload: dict[str, Any], digest_key: str) -> str:
    canonical = dict(payload)
    canonical.pop(digest_key, None)
    return sha256_bytes(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode())


def read_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def validate_zip(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError("immutable source ZIP is missing")
    size = path.stat().st_size
    digest = sha256_file(path)
    if size != ARTIFACT_SIZE:
        raise ValueError(f"source ZIP size mismatch: {size}")
    if digest != ARTIFACT_SHA256:
        raise ValueError(f"source ZIP SHA-256 mismatch: {digest}")
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"source ZIP CRC failure: {bad_member}")
    return {"artifact_id": ARTIFACT_ID, "size_bytes": size, "sha256": digest, "crc": "OK"}


def validate_source_artifact(
    root: Path, *, source_zip: Path | None = None, strict_hashes: bool = True
) -> dict[str, Any]:
    zip_evidence = validate_zip(source_zip) if source_zip is not None else {
        "artifact_id": ARTIFACT_ID, "sha256": ARTIFACT_SHA256, "size_bytes": ARTIFACT_SIZE,
        "verification": "ZIP_VALIDATED_BY_WORKFLOW",
    }
    observed: dict[str, str] = {}
    for name, expected in EXPECTED_FILES.items():
        path = root / name
        if not path.is_file():
            raise ValueError(f"source artifact is missing {name}")
        observed[name] = sha256_file(path)
        if strict_hashes and observed[name] != expected:
            raise ValueError(f"source artifact SHA-256 mismatch for {name}")
    allowed_root = set(EXPECTED_FILES) | {"wheelhouse"}
    actual_root = {p.name for p in root.iterdir()}
    if actual_root != allowed_root or not (root / "wheelhouse").is_dir():
        raise ValueError(f"unexpected source artifact entries: {sorted(actual_root ^ allowed_root)}")

    manifest, response_bytes = read_json(root / "generation_manifest.json")
    responses_obj, response_bytes = read_json(root / "llm_responses_v3.json")
    truth, _ = read_json(root / "ground_truth_v3.json")
    prompts_obj, prompt_bytes = read_json(root / "prompts.json")
    snapshot, _ = read_json(root / "generation_snapshot.json")
    if not all(isinstance(x, dict) for x in (manifest, responses_obj, truth, prompts_obj, snapshot)):
        raise ValueError("source artifact JSON roots must be objects")

    for label, obj in (("manifest", manifest), ("snapshot", snapshot)):
        if obj.get("provider_name") != PROVIDER_NAME:
            raise ValueError(f"{label} provider identity mismatch")
        if obj.get("requested_model_id") != MODEL_ID or obj.get("provider_model_id") != MODEL_ID:
            raise ValueError(f"{label} model identity mismatch")
    if manifest.get("evaluation_mode") != "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY":
        raise ValueError("original evaluation mode mismatch")
    if manifest.get("generation_snapshot_file") != "generation_snapshot.json":
        raise ValueError("manifest does not bind generation_snapshot.json")
    snapshot_hash = canonical_json_hash(snapshot, "snapshot_sha256")
    if snapshot.get("snapshot_sha256") != snapshot_hash:
        raise ValueError("generation_snapshot canonical SHA-256 mismatch")
    if manifest.get("generation_snapshot_sha256") != snapshot_hash:
        raise ValueError("manifest snapshot SHA-256 does not match snapshot")
    if sha256_bytes(response_bytes) != manifest.get("llm_responses_sha256"):
        raise ValueError("response file hash does not match generation manifest")
    prompt_hash = sha256_bytes(prompt_bytes)
    if prompt_hash != manifest.get("prompt_dataset_sha256"):
        raise ValueError("prompt file hash does not match generation manifest")
    if prompt_hash != truth.get("prompt_dataset_sha256"):
        raise ValueError("prompt hash does not match original Ground Truth")

    rows = responses_obj.get("samples")
    prompt_rows = prompts_obj.get("samples")
    truth_rows = truth.get("samples")
    snapshot_rows = snapshot.get("packages")
    if not all(isinstance(x, list) and len(x) == 100 for x in
               (rows, prompt_rows, truth_rows, snapshot_rows)):
        raise ValueError("response, prompt, Ground Truth and snapshot cohorts must each contain 100 rows")
    by_id: dict[str, dict[str, Any]] = {}
    for row in truth_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sample_id"), str):
            raise ValueError("Ground Truth rows require sample_id")
        if row["sample_id"] in by_id:
            raise ValueError("duplicate Ground Truth sample_id")
        by_id[row["sample_id"]] = row
    prompt_by_id = {r.get("sample_id"): r for r in prompt_rows if isinstance(r, dict)}
    snapshot_by_id = {r.get("sample_id"): r for r in snapshot_rows if isinstance(r, dict)}
    if len(prompt_by_id) != 100 or len(snapshot_by_id) != 100:
        raise ValueError("duplicate or malformed prompt/snapshot sample IDs")

    expected_wheels: dict[str, str] = {}
    response_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sample_id"), str):
            raise ValueError("response rows require sample_id")
        sample_id = row["sample_id"]
        response_ids.append(sample_id)
        gt, prompt, snap_row = by_id.get(sample_id), prompt_by_id.get(sample_id), snapshot_by_id.get(sample_id)
        if gt is None or prompt is None or snap_row is None:
            raise ValueError(f"cohort identity mismatch for {sample_id}")
        for key in ("package_name", "prompt"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"response {key} missing for {sample_id}")
            if row[key] != gt.get(key) or row[key] != prompt.get(key) or row[key] != snap_row.get("package_name"):
                if key == "package_name" or row.get(key) != gt.get(key) or row.get(key) != prompt.get(key):
                    raise ValueError(f"{key} mismatch across source files for {sample_id}")
        if type(gt.get("pypi_exists")) is not bool:
            raise ValueError(f"original package-existence label is not boolean for {sample_id}")
        label = "CLEAN" if gt["pypi_exists"] else "HALLUCINATION"
        if gt.get("ground_truth") != label:
            raise ValueError(f"original package label conflict for {sample_id}")
        resolution = snap_row.get("resolution_status")
        if resolution == "RESOLVED":
            relative = snap_row.get("wheel_relative_path")
            wheel_name = snap_row.get("wheel_filename")
            digest = snap_row.get("wheel_sha256")
            if not isinstance(relative, str) or not isinstance(wheel_name, str):
                raise ValueError(f"resolved snapshot row lacks wheel identity: {sample_id}")
            wheel_path = Path(relative)
            if wheel_path.is_absolute() or ".." in wheel_path.parts or wheel_path.parts[0] != "wheelhouse":
                raise ValueError(f"unsafe wheel path in snapshot: {relative}")
            actual = root / wheel_path
            if not actual.is_file() or actual.name != wheel_name:
                raise ValueError(f"snapshot wheel is missing or misnamed: {relative}")
            observed_hash = sha256_file(actual)
            if observed_hash != digest or snap_row.get("wheel_sha256_observed") != digest:
                raise ValueError(f"original wheel SHA-256 mismatch: {relative}")
            expected_wheels[relative] = digest
        elif resolution != "UNRESOLVED":
            raise ValueError(f"unknown snapshot resolution status for {sample_id}: {resolution}")

    if len(set(response_ids)) != 100 or set(response_ids) != set(by_id) or set(response_ids) != set(prompt_by_id) or set(response_ids) != set(snapshot_by_id):
        raise ValueError("source sample ID sets are not exactly aligned and unique")
    actual_wheels = {
        str(path.relative_to(root)).replace(os.sep, "/"): sha256_file(path)
        for path in (root / "wheelhouse").rglob("*") if path.is_file()
    }
    if actual_wheels != expected_wheels:
        raise ValueError("original wheelhouse file set or SHA-256 differs from generation_snapshot.json")

    statuses = Counter(row.get("request_status") for row in rows)
    if dict(statuses) != EXPECTED_STATUS_COUNTS:
        raise ValueError(f"unexpected original response status distribution: {dict(statuses)}")
    expected_counts = {"request_count": 100, "successful_requests": 21,
                       "abstained_requests": 77, "failed_requests": 2}
    if any(manifest.get(k) != v for k, v in expected_counts.items()):
        raise ValueError("generation manifest counts do not match immutable response cohort")
    return {
        "manifest": manifest, "responses": rows, "truth_by_id": by_id,
        "prompt_by_id": prompt_by_id, "snapshot_by_id": snapshot_by_id,
        "snapshot": snapshot, "prompt_hash": prompt_hash, "file_sha256": observed,
        "status_counts": dict(statuses), "zip_evidence": zip_evidence,
    }


def prepare_requirements(
    root: Path, requirements_path: Path, pins_path: Path,
    *, source_zip: Path | None = None, strict_hashes: bool = True
) -> list[dict[str, str]]:
    validated = validate_source_artifact(root, source_zip=source_zip, strict_hashes=strict_hashes)
    pins: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for response in validated["responses"]:
        if response.get("request_status") != "SUCCESS":
            continue
        sample_id = response["sample_id"]
        snap = validated["snapshot_by_id"][sample_id]
        if snap.get("resolution_status") != "RESOLVED":
            continue
        name, version = snap.get("package_name"), snap.get("pypi_version")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise ValueError(f"unsafe distribution name in snapshot: {name!r}")
        if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version):
            raise ValueError(f"invalid exact package version in snapshot: {version!r}")
        requirement = f"{name}=={version}"
        if name.lower().replace("_", "-") in seen and seen[name.lower().replace("_", "-")] != version:
            raise ValueError(f"conflicting snapshot versions for {name}")
        seen[name.lower().replace("_", "-")] = version
        pins.append({
            "sample_id": sample_id, "package_name": name, "version": version,
            "requirement": requirement,
            "snapshot_wheel_filename": str(snap["wheel_filename"]),
            "snapshot_wheel_sha256": str(snap["wheel_sha256"]),
        })
    if not pins:
        raise ValueError("no SUCCESS samples have exact resolved package versions in snapshot")
    pins.sort(key=lambda item: item["sample_id"])
    requirements_path.parent.mkdir(parents=True, exist_ok=True)
    requirements_path.write_text("".join(f"{p['requirement']}\n" for p in pins), encoding="utf-8")
    pins_path.write_text(json.dumps({"schema_version": "jamp.hunt.recovery-pins.v1",
                                     "target": "CPython 3.11 Linux x86_64",
                                     "pins": pins}, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    tsv = requirements_path.with_suffix(".tsv")
    tsv.write_text("".join(f"{p['sample_id']}\t{p['package_name']}\t{p['version']}\n"
                           for p in pins), encoding="utf-8")
    return pins


def _wheel_compatibility(filename: str) -> tuple[str, str, bool]:
    try:
        from pip._vendor.packaging.tags import sys_tags
        from pip._vendor.packaging.utils import parse_wheel_filename
        name, version, _build, tags = parse_wheel_filename(filename)
        compatible = bool(set(tags).intersection(set(sys_tags())))
        return str(name), str(version), compatible
    except Exception as exc:
        raise ValueError(f"invalid wheel filename {filename}: {exc}") from exc


def build_wheel_manifest(
    wheelhouse: Path, pins_path: Path, download_status_path: Path, output: Path
) -> dict[str, Any]:
    pins_obj, _ = read_json(pins_path)
    pins = pins_obj.get("pins") if isinstance(pins_obj, dict) else None
    if not isinstance(pins, list):
        raise ValueError("pins manifest is invalid")
    status: dict[str, str] = {}
    if download_status_path.is_file():
        for line in download_status_path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                status[parts[0]] = parts[1]
    samples: dict[str, Any] = {}
    wheel_records: list[dict[str, Any]] = []
    for pin in pins:
        sample_id = pin["sample_id"]
        folder = wheelhouse / sample_id
        files = sorted(folder.glob("*.whl")) if folder.is_dir() else []
        direct = None
        records = []
        for path in files:
            name, version, compatible = _wheel_compatibility(path.name)
            record = {"sample_id": sample_id, "filename": path.name,
                      "relative_path": f"{sample_id}/{path.name}",
                      "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                      "distribution": name, "version": version,
                      "compatible_cpython311_linux_x86_64": compatible}
            records.append(record)
            wheel_records.append(record)
            if (name.lower().replace("_", "-") == pin["package_name"].lower().replace("_", "-")
                    and version == pin["version"] and compatible):
                direct = record
        if direct is None:
            samples[sample_id] = {
                "status": "INCONCLUSIVE",
                "reason": "no_compatible_wheel" if status.get(sample_id) == "SUCCESS"
                          else "wheel_download_failed",
                "download_status": status.get(sample_id, "MISSING"),
                "direct_wheel": None, "wheels": records,
            }
        else:
            samples[sample_id] = {
                "status": "READY", "reason": "exact_pinned_compatible_wheel_found",
                "download_status": status.get(sample_id, "SUCCESS"),
                "direct_wheel": direct, "wheels": records,
            }
    unexpected = [p.name for p in wheelhouse.iterdir() if not p.is_dir()]
    if unexpected:
        raise ValueError(f"wheelhouse root contains unexpected files: {unexpected}")
    manifest = {
        "schema_version": "jamp.hunt.recovery-wheelhouse.v2",
        "target": "CPython 3.11 Linux x86_64",
        "wheel_count": len(wheel_records), "wheels": wheel_records,
        "samples": samples,
        "wheelhouse_sha256": sha256_bytes(json.dumps(wheel_records, sort_keys=True,
                                                        separators=(",", ":")).encode()),
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def analyze_code(code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tree = ast.parse(code)
    aliases: dict[str, tuple[str, tuple[str, ...]]] = {}
    importlib_names = {"importlib"}
    import_module_names = {"__import__"}
    probes: dict[tuple[str, tuple[str, ...]], bool] = {}
    unresolved_dynamic: list[dict[str, Any]] = []

    def add(module: str, attrs: tuple[str, ...], callable_required: bool = False) -> None:
        key = (module, attrs)
        probes[key] = probes.get(key, False) or callable_required

    def resolve(node: ast.expr) -> tuple[str, tuple[str, ...]] | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name) or current.id not in aliases:
            return None
        module, prefix = aliases[current.id]
        return module, prefix + tuple(reversed(parts))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                bound = item.asname or item.name.split(".", 1)[0]
                module = item.name if item.asname else bound
                aliases[bound] = (module, ())
                if item.name == "importlib":
                    importlib_names.add(bound)
                add(item.name, ())
        elif isinstance(node, ast.ImportFrom) and node.module:
            add(node.module, ())
            if node.module == "importlib":
                for item in node.names:
                    if item.name == "import_module":
                        import_module_names.add(item.asname or item.name)
            for item in node.names:
                if item.name != "*":
                    bound = item.asname or item.name
                    aliases[bound] = (node.module, (item.name,))
                    add(node.module, (item.name,))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            result = resolve(node)
            if result:
                add(*result)
        elif isinstance(node, ast.Call):
            result = resolve(node.func)
            if result:
                add(*result, callable_required=True)
            elif isinstance(node.func, ast.Name) and node.func.id in aliases:
                module, attrs = aliases[node.func.id]
                add(module, attrs, callable_required=True)
            is_dynamic = (
                isinstance(node.func, ast.Name) and node.func.id in import_module_names
            ) or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in importlib_names
            ) or (
                isinstance(node.func, ast.Name) and node.func.id == "__import__"
            )
            if is_dynamic:
                arg = node.args[0] if node.args else None
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
                    add(arg.value, ())
                else:
                    unresolved_dynamic.append({
                        "line": getattr(node, "lineno", None),
                        "reason": "dynamic_import_target_not_static",
                    })
    probes_list = [
        {"module": module, "attributes": list(attrs), "callable": required}
        for (module, attrs), required in sorted(probes.items())
    ]
    return probes_list, unresolved_dynamic


def extract_api_probes(code: str) -> list[dict[str, Any]]:
    return analyze_code(code)[0]


def _child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run_api_probe(
    probes: list[dict[str, Any]], python_executable: str | None = None
) -> dict[str, Any]:
    if not probes:
        return {"api_valid": None, "reason": "no_static_api_references"}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [python_executable or sys.executable, "-I", "-c", PROBE_SOURCE,
             json.dumps(probes, sort_keys=True)],
            capture_output=True, text=True, timeout=25, check=False,
            preexec_fn=_child_limits,
            env={"PATH": os.environ.get("PATH", ""), "HOME": "/tmp", "TMPDIR": "/tmp",
                 "PYTHONNOUSERSITE": "1"},
        )
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as exc:
        return {"api_valid": None, "reason": "probe_execution_failed",
                "error_type": type(exc).__name__}
    if completed.returncode != 0:
        return {"api_valid": None, "reason": "probe_process_failed",
                "returncode": completed.returncode, "stderr": completed.stderr[-1000:]}
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        return {"api_valid": None, "reason": "invalid_probe_output"}
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError:
        return {"api_valid": None, "reason": "invalid_probe_json"}
    if not isinstance(result, dict) or result.get("api_valid") not in (True, False, None):
        return {"api_valid": None, "reason": "invalid_probe_schema"}
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def install_sample_environment(
    sample_id: str, requirement: str, wheelhouse: Path
) -> str | None:
    folder = wheelhouse / sample_id
    if not folder.is_dir() or not list(folder.glob("*.whl")):
        return None
    with tempfile.TemporaryDirectory(prefix="jamp-hunt-recovery-") as tmp:
        env_dir = Path(tmp) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        python = env_dir / "bin" / "python"
        installed = subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check",
             "--no-input", "--no-index", "--only-binary=:all:",
             "--find-links", str(folder), requirement],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if installed.returncode != 0:
            return None
        # Keep the venv alive while the caller probes it.
        persistent = Path(tempfile.mkdtemp(prefix="jamp-hunt-env-"))
        import shutil
        shutil.copytree(env_dir, persistent / "venv", dirs_exist_ok=True)
        return str(persistent / "venv" / "bin" / "python")


def evaluate(
    root: Path, wheelhouse: Path, pins_path: Path, wheel_manifest_path: Path,
    output_dir: Path, *, source_zip: Path | None = None,
    probe_runner=run_api_probe, installer=install_sample_environment,
    strict_hashes: bool = True,
) -> dict[str, Any]:
    validated = validate_source_artifact(root, source_zip=source_zip, strict_hashes=strict_hashes)
    pins_obj, _ = read_json(pins_path)
    wheel_manifest, _ = read_json(wheel_manifest_path)
    pins = {p["sample_id"]: p for p in pins_obj.get("pins", [])}
    wheel_samples = wheel_manifest.get("samples", {})
    api_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for sample in validated["responses"]:
        sample_id = sample["sample_id"]
        gt = validated["truth_by_id"][sample_id]
        snap = validated["snapshot_by_id"][sample_id]
        status = sample.get("request_status")
        code = sample.get("code")
        probes: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        evidence: dict[str, Any]
        if status != "SUCCESS":
            evidence = {"api_valid": None, "reason": f"generation_{str(status).lower()}_no_candidate_code"}
        elif not isinstance(code, str) or not code.strip():
            evidence = {"api_valid": None, "reason": "successful_response_missing_code"}
        else:
            try:
                probes, unresolved = analyze_code(code)
            except SyntaxError as exc:
                evidence = {"api_valid": None, "reason": "candidate_code_syntax_error",
                            "line": exc.lineno}
            else:
                if unresolved:
                    evidence = {"api_valid": None, "reason": "unresolved_dynamic_import",
                                "dynamic_imports": unresolved}
                elif snap.get("resolution_status") != "RESOLVED" or sample_id not in pins:
                    evidence = {"api_valid": None, "reason": "snapshot_version_unresolved"}
                else:
                    wheel_status = wheel_samples.get(sample_id, {})
                    if wheel_status.get("status") != "READY":
                        evidence = {"api_valid": None,
                                    "reason": wheel_status.get("reason", "no_compatible_wheel")}
                    else:
                        pin = pins[sample_id]
                        python = installer(sample_id, pin["requirement"], wheelhouse)
                        if python is None:
                            evidence = {"api_valid": None,
                                        "reason": "isolated_install_failed_or_dependency_unavailable"}
                        else:
                            evidence = probe_runner(probes, python)

        api_value = evidence.get("api_valid")
        api_status = "VALID" if api_value is True else "INVALID" if api_value is False else "INCONCLUSIVE"
        raw_response = json.dumps(sample, sort_keys=True, separators=(",", ":")).encode()
        raw_prompt = json.dumps(validated["prompt_by_id"][sample_id],
                                sort_keys=True, separators=(",", ":")).encode()
        api_record = {
            "sample_id": sample_id, "package_name": gt["package_name"],
            "generation_status": status, "package_exists": gt["pypi_exists"],
            "api_valid": api_value, "api_status": api_status,
            "probes": probes, "probe_count": len(probes), "evidence": evidence,
            "provenance": {
                "source_artifact_id": ARTIFACT_ID,
                "source_artifact_sha256": ARTIFACT_SHA256,
                "response_file": "llm_responses_v3.json",
                "response_row_sha256": sha256_bytes(raw_response),
                "prompt_file": "prompts.json",
                "prompt_row_sha256": sha256_bytes(raw_prompt),
                "ground_truth_file": "ground_truth_v3.json",
                "original_package_gt": gt["ground_truth"],
                "snapshot_file": "generation_snapshot.json",
                "snapshot_sha256": validated["snapshot"]["snapshot_sha256"],
                "snapshot_package_record": snap,
                "recovery_wheel_manifest_sha256": sha256_file(wheel_manifest_path),
                "recovery_wheels": wheel_samples.get(sample_id, {}).get("wheels", []),
                "api_method": "AST_STATIC_IMPORT_ATTRIBUTE_CALLABILITY_RUNTIME_PROBE",
                "api_scope_excludes": ["function_signatures", "behavioral_compatibility"],
            },
        }
        api_rows.append(api_record)
        results.append({
            "sample_id": sample_id, "package_name": gt["package_name"],
            "package_exists": gt["pypi_exists"], "package_ground_truth": gt["ground_truth"],
            "api_valid": api_value, "api_ground_truth": api_status,
            "generation_status": status, "api_evidence_ref": sample_id,
        })

    counts = Counter(row["api_status"] for row in api_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "jamp-hunt-recovery-results-v0.3",
        "source_artifact_id": ARTIFACT_ID, "source_artifact_sha256": ARTIFACT_SHA256,
        "source_artifact_size_bytes": ARTIFACT_SIZE,
        "source_file_sha256": validated["file_sha256"],
        "source_zip_evidence": validated["zip_evidence"],
        "snapshot_sha256": validated["snapshot"]["snapshot_sha256"],
        "wheel_manifest_sha256": sha256_file(wheel_manifest_path),
        "provider_name": PROVIDER_NAME, "requested_model_id": MODEL_ID,
        "provider_model_id": MODEL_ID,
        "api_ground_truth_method": "AST_STATIC_IMPORT_ATTRIBUTE_CALLABILITY_RUNTIME_PROBE",
        "api_validity_scope": "Importability, referenced symbol/attribute presence and callability only; not signatures or behavior.",
        "generated_model_code_executed": False,
        "package_existence_and_api_validity_are_separate_axes": True,
        "runtime_snapshot_note": "API reachability is observed in this recovery runtime, not retroactively at generation time.",
        "request_status_counts": validated["status_counts"],
        "api_ground_truth_counts": dict(counts),
        "attempted_sample_count": len(results),
        "api_probe_eligible_count": sum(r["generation_status"] == "SUCCESS" for r in results),
        "qualification": "NOT_GRANTED",
        "recovery_execution": {
            "github_run_id": os.environ.get("JAMP_RECOVERY_RUN_ID"),
            "github_sha": os.environ.get("JAMP_RECOVERY_SHA"),
            "github_workflow": os.environ.get("JAMP_RECOVERY_WORKFLOW"),
            "sandbox_image_id": os.environ.get("JAMP_SANDBOX_IMAGE_ID"),
        },
        "runtime_environment": {"python_version": platform.python_version(),
                                "platform": platform.platform(),
                                "implementation": platform.python_implementation()},
        "results": results,
    }
    api_gt = {
        "schema_version": "jamp-hunt-api-ground-truth-v0.3",
        "source_artifact_id": ARTIFACT_ID, "source_artifact_sha256": ARTIFACT_SHA256,
        "provider_name": PROVIDER_NAME, "model_id": MODEL_ID,
        "snapshot_sha256": validated["snapshot"]["snapshot_sha256"],
        "method": report["api_ground_truth_method"],
        "api_validity_scope": report["api_validity_scope"],
        "runtime_snapshot_note": report["runtime_snapshot_note"],
        "wheel_manifest_sha256": report["wheel_manifest_sha256"],
        "request_status_counts": validated["status_counts"],
        "api_ground_truth_counts": dict(counts),
        "qualification": "NOT_GRANTED", "samples": api_rows,
    }
    (output_dir / "api_ground_truth_v0.3.json").write_text(
        json.dumps(api_gt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "results_v0.3.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--artifact-dir", type=Path, required=True)
    prepare.add_argument("--source-zip", type=Path, required=True)
    prepare.add_argument("--requirements", type=Path, required=True)
    prepare.add_argument("--pins", type=Path, required=True)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("--wheelhouse", type=Path, required=True)
    manifest.add_argument("--pins", type=Path, required=True)
    manifest.add_argument("--download-status", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("evaluate")
    run.add_argument("--artifact-dir", type=Path, required=True)
    run.add_argument("--wheelhouse", type=Path, required=True)
    run.add_argument("--pins", type=Path, required=True)
    run.add_argument("--wheelhouse-manifest", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        pins = prepare_requirements(args.artifact_dir, args.requirements, args.pins,
                                    source_zip=args.source_zip)
        print(json.dumps({"artifact_id": ARTIFACT_ID, "pin_count": len(pins),
                          "requirements": [p["requirement"] for p in pins]}, sort_keys=True))
    elif args.command == "manifest":
        result = build_wheel_manifest(args.wheelhouse, args.pins, args.download_status, args.output)
        print(json.dumps({"wheel_count": result["wheel_count"],
                          "ready_samples": sum(v["status"] == "READY" for v in result["samples"].values()),
                          "inconclusive_samples": sum(v["status"] == "INCONCLUSIVE" for v in result["samples"].values())},
                         sort_keys=True))
    else:
        report = evaluate(args.artifact_dir, args.wheelhouse, args.pins,
                          args.wheelhouse_manifest, args.output_dir)
        print(json.dumps({"attempted_sample_count": report["attempted_sample_count"],
                          "api_ground_truth_counts": report["api_ground_truth_counts"],
                          "qualification": report["qualification"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
