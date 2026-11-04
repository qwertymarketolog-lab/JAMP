"""Recover The Hunt v0.3 results from the immutable Nemotron artifact.

Generated model code is never executed. Only AST-derived import and attribute
reachability probes run in a network-isolated, resource-bounded child process.
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
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

ARTIFACT_ID = 13257610773
ARTIFACT_SHA256 = "9e0ff74b4f3450044224fc457ef9dae8f831c77773852dc9bf985a846be7c5a3"
EXPECTED_FILES = {
    "generation_manifest.json": "ac60a60e331145e270dbfb02fd56d85022ff6139fa3a314049ffca8eb21e17b7",
    "llm_responses_v3.json": "10c1031fac24f40a57978bc2a6b4a58253ed728ced2c284381d2b6f31578d20b",
    "ground_truth_v3.json": "56bbd14c435beb698e570bccadcca0fcd954b91012408768944ed482b499bb4d",
    "prompts.json": "7d9721ac6ce6d2235d42a447971e31f5143fe50d246549673253309de927c9d8",
}
PROBE_SOURCE = r'''import importlib, json, sys
probes = json.loads(sys.argv[1])
missing = []
for probe in probes:
    module_name = probe["module"]
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name or module_name.startswith(str(exc.name) + "."):
            missing.append({"probe": probe, "kind": "missing_module", "error": str(exc)[:500]})
            continue
        print(json.dumps({
            "api_valid": None,
            "reason": "dependency_import_failed",
            "error": str(exc)[:500],
        }))
        raise SystemExit(0)
    except Exception as exc:
        print(json.dumps({
            "api_valid": None,
            "reason": "module_import_failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }))
        raise SystemExit(0)
    current = module
    try:
        for part in probe.get("attributes", []):
            try:
                current = getattr(current, part)
            except AttributeError:
                try:
                    current = importlib.import_module(module_name + "." + part)
                except ModuleNotFoundError as exc:
                    expected_submodule = module_name + "." + part
                    if (
                        exc.name == expected_submodule
                        or expected_submodule.startswith(str(exc.name) + ".")
                    ):
                        missing.append({
                            "probe": probe,
                            "kind": "missing_attribute_or_submodule",
                            "error": str(exc)[:500],
                        })
                        break
                    raise
        if probe.get("callable") and not callable(current):
            missing.append({"probe": probe, "kind": "symbol_not_callable"})
    except AttributeError as exc:
        missing.append({"probe": probe, "kind": "missing_attribute", "error": str(exc)[:500]})
    except Exception as exc:
        print(json.dumps({
            "api_valid": None,
            "reason": "attribute_resolution_failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }))
        raise SystemExit(0)
if missing:
    print(json.dumps({
        "api_valid": False,
        "reason": "api_symbol_missing",
        "missing": missing,
    }, sort_keys=True))
else:
    print(json.dumps({
        "api_valid": True,
        "reason": "all_imports_and_referenced_module_attributes_resolved",
    }, sort_keys=True))
'''


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def validate_source_artifact(root: Path, *, strict_hashes: bool = True) -> dict[str, Any]:
    observed: dict[str, str] = {}
    for name, expected in EXPECTED_FILES.items():
        path = root / name
        if not path.is_file():
            raise ValueError(f"source artifact is missing {name}")
        observed[name] = sha256_file(path)
        if strict_hashes and observed[name] != expected:
            raise ValueError(f"source artifact SHA-256 mismatch for {name}")
    extra = {p.name for p in root.iterdir() if p.is_file()} - set(EXPECTED_FILES)
    if extra:
        raise ValueError(f"unexpected files in source artifact: {sorted(extra)}")
    manifest, _ = read_json(root / "generation_manifest.json")
    responses, response_bytes = read_json(root / "llm_responses_v3.json")
    truth, _ = read_json(root / "ground_truth_v3.json")
    prompts, prompt_bytes = read_json(root / "prompts.json")
    if not all(isinstance(item, dict) for item in (manifest, responses, truth, prompts)):
        raise ValueError("source artifact JSON roots must be objects")
    if manifest.get("provider_name") != "anymodel":
        raise ValueError("source provider does not match the original Nemotron artifact")
    if manifest.get("requested_model_id") != "am/nemotron-3-ultra-550b-a55b":
        raise ValueError("source requested model does not match the original Nemotron artifact")
    if manifest.get("provider_model_id") != "am/nemotron-3-ultra-550b-a55b":
        raise ValueError("source provider model does not match the original Nemotron artifact")
    if manifest.get("evaluation_mode") != "LIVE_LLM_PYPI_PACKAGE_EXISTENCE_ONLY":
        raise ValueError("source evaluation mode is not the original package-existence-only mode")
    if truth.get("label_scope") != (
        "distribution existence only; API correctness is not ground truth"
    ):
        raise ValueError("original Ground Truth label scope changed")
    if sha256_bytes(response_bytes) != manifest.get("llm_responses_sha256"):
        raise ValueError("response file hash does not match generation manifest")
    prompt_hash = sha256_bytes(prompt_bytes)
    if prompt_hash != manifest.get("prompt_dataset_sha256"):
        raise ValueError("prompt file hash does not match generation manifest")
    if prompt_hash != truth.get("prompt_dataset_sha256"):
        raise ValueError("prompt hash does not match original Ground Truth metadata")
    samples = responses.get("samples")
    prompt_rows = prompts.get("samples")
    truth_rows = truth.get("samples")
    cohorts = (samples, prompt_rows, truth_rows)
    if not all(isinstance(rows, list) and len(rows) == 100 for rows in cohorts):
        raise ValueError(
            "original response, prompt, and Ground Truth cohorts must each have 100 rows"
        )
    by_id: dict[str, dict[str, Any]] = {}
    for row in truth_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sample_id"), str):
            raise ValueError("Ground Truth rows require sample_id")
        if row["sample_id"] in by_id:
            raise ValueError("duplicate Ground Truth sample_id")
        by_id[row["sample_id"]] = row
    prompt_by_id = {row.get("sample_id"): row for row in prompt_rows if isinstance(row, dict)}
    response_ids: list[str] = []
    for row in samples:
        if not isinstance(row, dict) or not isinstance(row.get("sample_id"), str):
            raise ValueError("response rows require sample_id")
        sample_id = row["sample_id"]
        response_ids.append(sample_id)
        gt = by_id.get(sample_id)
        prompt = prompt_by_id.get(sample_id)
        if gt is None or prompt is None:
            raise ValueError(f"cohort identity mismatch for {sample_id}")
        for key in ("package_name", "prompt"):
            if not isinstance(row.get(key), str) or not row.get(key):
                raise ValueError(f"response {key} must be a non-empty string for {sample_id}")
            if key == "package_name" and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]*", row[key]
            ):
                raise ValueError(f"unsafe or invalid distribution name for {sample_id}")
            if row.get(key) != gt.get(key) or row.get(key) != prompt.get(key):
                raise ValueError(f"{key} mismatch across original cohort for {sample_id}")
        if type(gt.get("pypi_exists")) is not bool:
            raise ValueError(f"original package-existence label is not boolean for {sample_id}")
        expected_label = "CLEAN" if gt["pypi_exists"] else "HALLUCINATION"
        if gt.get("ground_truth") != expected_label:
            raise ValueError(f"package-existence label conflict for {sample_id}")
    id_sets_match = (
        len(set(response_ids)) == 100
        and set(response_ids) == set(by_id)
        and set(response_ids) == set(prompt_by_id)
    )
    if not id_sets_match:
        raise ValueError("original sample ID sets are not exactly aligned and unique")
    statuses = Counter(row.get("request_status") for row in samples)
    if statuses != Counter({"SUCCESS": 18, "ABSTAINED": 81, "FAILED": 1}):
        raise ValueError(f"unexpected original response status distribution: {dict(statuses)}")
    expected_counts = {
        "request_count": 100,
        "successful_requests": 18,
        "abstained_requests": 81,
        "failed_requests": 1,
    }
    if any(manifest.get(key) != value for key, value in expected_counts.items()):
        raise ValueError("original generation manifest counts do not match response cohort")
    return {
        "manifest": manifest,
        "responses": samples,
        "truth_by_id": by_id,
        "prompt_hash": prompt_hash,
        "file_sha256": observed,
        "status_counts": dict(statuses),
    }


def extract_api_probes(code: str) -> list[dict[str, Any]]:
    """Return AST-derived import, attribute, and callability probes only."""
    tree = ast.parse(code)
    aliases: dict[str, tuple[str, tuple[str, ...]]] = {}
    probes: dict[tuple[str, tuple[str, ...]], bool] = {}

    def add_probe(
        module: str,
        attributes: tuple[str, ...],
        callable_required: bool = False,
    ) -> None:
        key = (module, attributes)
        probes[key] = probes.get(key, False) or callable_required

    def resolve_expression(node: ast.expr) -> tuple[str, tuple[str, ...]] | None:
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
                add_probe(item.name, ())
        elif isinstance(node, ast.ImportFrom) and node.module:
            add_probe(node.module, ())
            for item in node.names:
                if item.name == "*":
                    continue
                bound = item.asname or item.name
                aliases[bound] = (node.module, (item.name,))
                add_probe(node.module, (item.name,))

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            resolved = resolve_expression(node)
            if resolved is not None:
                add_probe(*resolved)
        elif isinstance(node, ast.Call):
            resolved = resolve_expression(node.func)
            if resolved is not None:
                add_probe(*resolved, callable_required=True)
            elif isinstance(node.func, ast.Name) and node.func.id in aliases:
                module, attributes = aliases[node.func.id]
                add_probe(module, attributes, callable_required=True)

    return [
        {"module": module, "attributes": list(attributes), "callable": callable_required}
        for (module, attributes), callable_required in sorted(probes.items())
    ]


def _child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    file_size = 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run_api_probe(probes: list[dict[str, Any]]) -> dict[str, Any]:
    if not probes:
        return {"api_valid": None, "reason": "no_importable_api_references"}
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", PROBE_SOURCE, json.dumps(probes, sort_keys=True)],
            capture_output=True, text=True, timeout=25, check=False,
            preexec_fn=_child_limits,
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.environ.get("HOME", "/tmp"),
                "TMPDIR": "/tmp",
                "MPLCONFIGDIR": "/tmp/matplotlib",
                "XDG_CACHE_HOME": "/tmp/cache",
                "PYTHONNOUSERSITE": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return {
            "api_valid": None,
            "reason": "probe_timeout",
            "duration_seconds": round(time.monotonic() - started, 3),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "api_valid": None,
            "reason": "probe_execution_error",
            "error_type": type(exc).__name__,
        }
    if completed.returncode != 0:
        return {
            "api_valid": None,
            "reason": "probe_process_failed",
            "returncode": completed.returncode,
            "stderr": completed.stderr[-1000:],
        }
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        return {
            "api_valid": None,
            "reason": "invalid_probe_output",
            "stdout": completed.stdout[-1000:],
        }
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError:
        return {"api_valid": None, "reason": "invalid_probe_json"}
    if not isinstance(result, dict) or result.get("api_valid") not in (True, False, None):
        return {"api_valid": None, "reason": "invalid_probe_schema"}
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def prepare_requirements(
    root: Path, output: Path, *, strict_hashes: bool = True
) -> list[str]:
    validated = validate_source_artifact(root, strict_hashes=strict_hashes)
    packages = sorted({
        validated["truth_by_id"][row["sample_id"]]["package_name"]
        for row in validated["responses"]
        if row.get("request_status") == "SUCCESS"
        and validated["truth_by_id"][row["sample_id"]].get("pypi_exists") is True
    })
    invalid = [name for name in packages if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]*", name
    )]
    if invalid:
        raise ValueError(f"unsafe or invalid distribution names in source Ground Truth: {invalid}")
    if not packages:
        raise ValueError("no successful response rows have existing package labels")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{name}\n" for name in packages), encoding="utf-8")
    return packages


def build_wheel_manifest(wheelhouse: Path, output: Path) -> dict[str, Any]:
    unexpected = [
        path.name
        for path in wheelhouse.iterdir()
        if not path.is_file() or not path.name.endswith(".whl")
    ]
    if unexpected:
        raise ValueError(f"wheelhouse contains unexpected entries: {sorted(unexpected)}")
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise ValueError("wheelhouse contains no wheel files")
    records = [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in wheels
    ]
    manifest = {
        "schema_version": "jamp.hunt.recovery-wheelhouse.v1",
        "wheel_count": len(records),
        "wheels": records,
        "wheelhouse_sha256": sha256_bytes(
            json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        ),
    }
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def evaluate(
    root: Path,
    wheelhouse: Path,
    wheelhouse_manifest_path: Path,
    output_dir: Path,
    probe_runner: Callable[[list[dict[str, Any]]], dict[str, Any]] = run_api_probe,
    *,
    strict_hashes: bool = True,
) -> dict[str, Any]:
    validated = validate_source_artifact(root, strict_hashes=strict_hashes)
    wheel_manifest, _ = read_json(wheelhouse_manifest_path)
    wheel_records = wheel_manifest.get("wheels") if isinstance(wheel_manifest, dict) else None
    if not isinstance(wheel_records, list) or not wheel_records:
        raise ValueError("wheelhouse manifest has no wheel records")
    observed_wheels = {
        path.name: sha256_file(path) for path in wheelhouse.glob("*.whl")
    }
    expected_wheels: dict[str, str] = {}
    for item in wheel_records:
        if not isinstance(item, dict):
            raise ValueError("wheelhouse manifest contains a non-object entry")
        filename, digest = item.get("filename"), item.get("sha256")
        if not isinstance(filename, str) or not filename.endswith(".whl"):
            raise ValueError("wheelhouse manifest contains an invalid wheel filename")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"wheelhouse manifest contains an invalid SHA-256 for {filename}")
        if filename in expected_wheels:
            raise ValueError(f"wheelhouse manifest contains duplicate filename: {filename}")
        expected_wheels[filename] = digest
    if observed_wheels != expected_wheels:
        raise ValueError("wheelhouse content differs from its SHA-256 manifest")
    canonical_wheels = [
        item for item in wheel_records if isinstance(item, dict)
    ]
    computed_wheelhouse_hash = sha256_bytes(
        json.dumps(
            canonical_wheels, sort_keys=True, separators=(",", ":")
        ).encode()
    )
    if computed_wheelhouse_hash != wheel_manifest.get("wheelhouse_sha256"):
        raise ValueError("wheelhouse manifest digest is internally inconsistent")

    api_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for sample in validated["responses"]:
        sample_id = sample["sample_id"]
        truth = validated["truth_by_id"][sample_id]
        status = sample.get("request_status")
        api: dict[str, Any]
        if status != "SUCCESS":
            api = {
                "api_valid": None,
                "reason": f"generation_{str(status).lower()}_no_candidate_code",
            }
            probes: list[dict[str, Any]] = []
        else:
            code = sample.get("code")
            if not isinstance(code, str) or not code.strip():
                api = {"api_valid": None, "reason": "successful_response_missing_code"}
                probes = []
            else:
                try:
                    probes = extract_api_probes(code)
                except SyntaxError as exc:
                    probes = []
                    api = {
                        "api_valid": None,
                        "reason": "candidate_code_syntax_error",
                        "line": exc.lineno,
                    }
                else:
                    api = probe_runner(probes)
        api_record = {
            "sample_id": sample_id,
            "package_name": truth["package_name"],
            "request_status": status,
            "package_exists": truth["pypi_exists"],
            "api_valid": api.get("api_valid"),
            "api_status": (
                "VALID" if api.get("api_valid") is True
                else "INVALID" if api.get("api_valid") is False
                else "INCONCLUSIVE"
            ),
            "probe_count": len(probes),
            "probes": probes,
            "evidence": api,
        }
        api_rows.append(api_record)
        results.append({
            "sample_id": sample_id,
            "package_name": truth["package_name"],
            "package_exists": truth["pypi_exists"],
            "package_ground_truth": truth["ground_truth"],
            "api_valid": api_record["api_valid"],
            "api_ground_truth": api_record["api_status"],
            "generation_status": status,
            "api_evidence_ref": sample_id,
        })

    api_counts = Counter(row["api_status"] for row in api_rows)
    report = {
        "schema_version": "jamp-hunt-recovery-results-v0.3",
        "source_artifact_id": ARTIFACT_ID,
        "source_artifact_sha256": ARTIFACT_SHA256,
        "source_manifest_sha256": sha256_file(root / "generation_manifest.json"),
        "source_responses_sha256": sha256_file(root / "llm_responses_v3.json"),
        "source_ground_truth_sha256": sha256_file(root / "ground_truth_v3.json"),
        "source_prompts_sha256": sha256_file(root / "prompts.json"),
        "wheel_manifest_sha256": sha256_file(wheelhouse_manifest_path),
        "prompt_dataset_sha256": validated["prompt_hash"],
        "api_ground_truth_method": (
            "AST_DERIVED_IMPORT_ATTRIBUTE_AND_CALLABILITY_REACHABILITY_"
            "IN_NETWORK_ISOLATED_SANDBOX"
        ),
        "api_validity_scope": (
            "Importability, imported symbol presence, referenced module attribute "
            "presence, and callability only; not signature or behavioral compatibility."
        ),
        "generated_model_code_executed": False,
        "package_existence_and_api_validity_are_separate_axes": True,
        "runtime_snapshot_note": (
            "API reachability is observed against the exact wheelhouse captured by "
            "this recovery run; it is not retroactively asserted for the generation timestamp."
        ),
        "qualification": "NOT_GRANTED",
        "recovery_execution": {
            "github_run_id": os.environ.get("JAMP_RECOVERY_RUN_ID"),
            "github_sha": os.environ.get("JAMP_RECOVERY_SHA"),
            "github_workflow": os.environ.get("JAMP_RECOVERY_WORKFLOW"),
            "sandbox_image_id": os.environ.get("JAMP_SANDBOX_IMAGE_ID"),
        },
        "runtime_environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "installed_distributions": sorted(
                {dist.metadata.get("Name", "unknown"): dist.version
                 for dist in importlib.metadata.distributions()}.items()
            ),
        },
        "request_status_counts": validated["status_counts"],
        "api_ground_truth_counts": dict(api_counts),
        "attempted_sample_count": len(results),
        "api_probe_eligible_count": sum(row["request_status"] == "SUCCESS" for row in api_rows),
        "results": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "api_ground_truth_v0.3.json").write_text(json.dumps({
        "schema_version": "jamp-hunt-api-ground-truth-v0.3",
        "source_artifact_id": ARTIFACT_ID,
        "method": report["api_ground_truth_method"],
        "api_validity_scope": report["api_validity_scope"],
        "runtime_snapshot_note": report["runtime_snapshot_note"],
        "wheel_manifest_sha256": sha256_file(wheelhouse_manifest_path),
        "api_ground_truth_counts": dict(api_counts),
        "samples": api_rows,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "results_v0.3.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--artifact-dir", type=Path, required=True)
    prepare.add_argument("--requirements", type=Path, required=True)
    manifest = sub.add_parser("manifest")
    manifest.add_argument("--wheelhouse", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("evaluate")
    run.add_argument("--artifact-dir", type=Path, required=True)
    run.add_argument("--wheelhouse", type=Path, required=True)
    run.add_argument("--wheelhouse-manifest", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        packages = prepare_requirements(args.artifact_dir, args.requirements)
        print(json.dumps({"package_count": len(packages), "packages": packages}, sort_keys=True))
    elif args.command == "manifest":
        result = build_wheel_manifest(args.wheelhouse, args.output)
        print(json.dumps({
            "wheel_count": result["wheel_count"],
            "wheelhouse_sha256": result["wheelhouse_sha256"],
        }, sort_keys=True))
    else:
        report = evaluate(
            args.artifact_dir,
            args.wheelhouse,
            args.wheelhouse_manifest,
            args.output_dir,
        )
        print(json.dumps({
            "attempted_sample_count": report["attempted_sample_count"],
            "api_probe_eligible_count": report["api_probe_eligible_count"],
            "api_ground_truth_counts": report["api_ground_truth_counts"],
            "qualification": report["qualification"],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
