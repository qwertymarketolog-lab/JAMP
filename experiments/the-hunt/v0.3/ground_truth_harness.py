"""Independent runtime Ground Truth diagnostics for The Hunt v0.3.2."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

TARGETS: dict[str, dict[str, str]] = {
    "celery": {
        "version": "5.6.3",
        "filename": "celery-5.6.3-py3-none-any.whl",
        "sha256": "0808f42f80909c4d5833202360ffafb2a4f83f4d8e23e1285d926610e9a7afa6",
    },
    "httpx": {
        "version": "0.28.1",
        "filename": "httpx-0.28.1-py3-none-any.whl",
        "sha256": "d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad",
    },
    "requests": {
        "version": "2.34.2",
        "filename": "requests-2.34.2-py3-none-any.whl",
        "sha256": "2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0",
    },
}
CASE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"case_id": "C01", "package": "celery", "module": "celery",
     "operation": "attribute", "attribute_path": ["Celery"],
     "description": "Celery public lazy export: celery.Celery",
     "static_call": {"module": "celery", "symbol_path": ["Celery"]}},
    {"case_id": "C02", "package": "celery", "module": "celery",
     "operation": "attribute", "attribute_path": ["shared_task"],
     "description": "Celery public lazy export: celery.shared_task",
     "static_call": {"module": "celery", "symbol_path": ["shared_task"]}},
    {"case_id": "C03", "package": "celery", "module": "celery.local",
     "operation": "attribute", "attribute_path": ["LazyModule"],
     "description": "Celery LazyModule class reachability",
     "static_call": {"module": "celery", "symbol_path": ["local", "LazyModule"]}},
    {"case_id": "C04", "package": "celery", "module": "celery.local",
     "operation": "attribute", "attribute_path": ["recreate_module"],
     "description": "Celery recreate_module function reachability",
     "static_call": {"module": "celery", "symbol_path": ["local", "recreate_module"]}},
    {"case_id": "C05", "package": "httpx", "module": "httpx",
     "operation": "attribute", "attribute_path": ["get"],
     "description": "HTTPX package-level function: httpx.get",
     "static_call": {"module": "httpx", "symbol_path": ["get"]}},
    {"case_id": "C06", "package": "httpx", "module": "httpx",
     "operation": "attribute", "attribute_path": ["Client"],
     "description": "HTTPX package-level class: httpx.Client",
     "static_call": {"module": "httpx", "symbol_path": ["Client"]}},
    {"case_id": "C07", "package": "httpx", "module": "httpx._api",
     "operation": "star_import", "statement": "from httpx._api import *",
     "symbol": "get", "description": "HTTPX star-import binding from httpx._api",
     "static_call": {"module": "httpx", "symbol_path": ["get"]}},
    {"case_id": "C08", "package": "httpx", "module": "httpx",
     "operation": "all_contains", "symbol": "get",
     "description": "HTTPX __all__ explicitly lists get", "static_call": None},
    {"case_id": "C09", "package": "requests", "module": "requests",
     "operation": "attribute", "attribute_path": ["get"],
     "description": "Requests package-level function: requests.get",
     "static_call": {"module": "requests", "symbol_path": ["get"]}},
    {"case_id": "C10", "package": "requests", "module": "requests",
     "operation": "all_contains", "symbol": "get",
     "description": "Requests __all__ explicitly lists get", "static_call": None},
    {"case_id": "C11", "package": "requests", "module": "requests",
     "operation": "attribute", "attribute_path": ["nonexistent_fn_xyz"],
     "description": "Negative control: missing Requests attribute",
     "static_call": {"module": "requests", "symbol_path": ["nonexistent_fn_xyz"]}},
    {"case_id": "C12", "package": "celery", "module": "celery",
     "operation": "attribute", "attribute_path": ["__jamp_missing_api_probe__"],
     "description": "Negative control: missing Celery dynamic export",
     "static_call": {"module": "celery", "symbol_path": ["__jamp_missing_api_probe__"]}},
)
SCHEMA_VERSION = "jamp.hunt.runtime-ground-truth.v1"
PROBE_SOURCE = r"""
import importlib
import json
import sys

case = json.loads(sys.argv[1])

def emit(api_valid, reason=None, error_type=None, error=None):
    print(json.dumps({
        "api_valid": api_valid, "reason": reason,
        "error_type": error_type, "error": error,
    }, sort_keys=True))

try:
    module = importlib.import_module(case["module"])
except Exception as exc:
    emit(None, "module_import_failed", type(exc).__name__, str(exc)[:1000])
    raise SystemExit(0)

try:
    operation = case["operation"]
    if operation == "attribute":
        current = module
        for part in case.get("attribute_path", []):
            current = getattr(current, part)
        emit(True)
    elif operation == "star_import":
        namespace = {}
        exec(case["statement"], namespace, namespace)
        emit(case["symbol"] in namespace)
    elif operation == "all_contains":
        names = getattr(module, "__all__", None)
        if not isinstance(names, (list, tuple, set)):
            emit(None, "all_missing_or_dynamic")
        else:
            emit(case["symbol"] in names)
    else:
        emit(None, "unsupported_probe_operation")
except AttributeError as exc:
    emit(False, "attribute_missing", type(exc).__name__, str(exc)[:1000])
except Exception as exc:
    emit(None, "probe_exception", type(exc).__name__, str(exc)[:1000])
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_target_metadata(manifest: dict[str, Any]) -> None:
    targets = manifest.get("targets")
    if not isinstance(targets, dict):
        raise ValueError("wheel manifest targets must be an object")
    for package, pin in TARGETS.items():
        record = targets.get(package)
        if not isinstance(record, dict):
            raise ValueError(f"wheel manifest missing target: {package}")
        for field in ("version", "filename", "sha256"):
            if record.get(field) != pin[field]:
                raise ValueError(
                    f"{package} target {field} mismatch: "
                    f"expected={pin[field]!r} observed={record.get(field)!r}"
                )


def _validate_wheelhouse(wheelhouse: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    records = manifest.get("wheelhouse")
    if not isinstance(records, list) or not records:
        raise ValueError("wheel manifest wheelhouse must be a non-empty list")
    expected: dict[str, str] = {}
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("wheelhouse manifest entry must be an object")
        filename, digest = item.get("filename"), item.get("sha256")
        if not isinstance(filename, str) or not filename.endswith(".whl"):
            raise ValueError("wheelhouse manifest contains a non-wheel filename")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"wheelhouse manifest has invalid SHA-256 for {filename}")
        if filename in expected:
            raise ValueError(f"duplicate wheelhouse filename: {filename}")
        expected[filename] = digest
    actual = {path.name for path in wheelhouse.glob("*.whl")}
    if actual != set(expected):
        raise ValueError(
            "wheelhouse file set differs from manifest: "
            f"missing={sorted(set(expected) - actual)} "
            f"extra={sorted(actual - set(expected))}"
        )
    for filename, digest in expected.items():
        if sha256_file(wheelhouse / filename) != digest:
            raise ValueError(f"wheelhouse SHA-256 mismatch: {filename}")
    return {name: wheelhouse / name for name in expected}


def _apply_child_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    memory_limit = 512 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    file_limit = 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _probe_api_valid(payload: Any) -> bool | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("api_valid")
    return value if type(value) is bool else None


def _run_runtime_probe(case: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", PROBE_SOURCE, json.dumps(case, sort_keys=True)],
            capture_output=True, text=True, timeout=12, check=False,
            preexec_fn=_apply_child_limits,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "api_valid": None, "reason": "probe_timeout",
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "stdout": str(exc.stdout or "")[-4000:],
            "stderr": str(exc.stderr or "")[-4000:],
        }
    except (OSError, ValueError) as exc:
        return {
            "api_valid": None, "reason": "probe_process_failed",
            "error_type": type(exc).__name__, "error": str(exc)[:1000],
            "elapsed_seconds": round(time.monotonic() - started, 4),
        }

    stdout, stderr = completed.stdout[-4000:], completed.stderr[-4000:]
    payload: Any = None
    try:
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if lines:
            payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        payload = None
    if completed.returncode != 0:
        return {
            "api_valid": None, "reason": "probe_nonzero_exit",
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "stdout": stdout, "stderr": stderr,
        }
    if not isinstance(payload, dict):
        return {
            "api_valid": None, "reason": "probe_output_invalid",
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "stdout": stdout, "stderr": stderr,
        }
    return {
        **payload, "api_valid": _probe_api_valid(payload),
        "returncode": completed.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 4),
        "stdout": stdout, "stderr": stderr,
    }


def _static_api_valid(status: Any) -> bool | None:
    if status == "EXISTS":
        return True
    if status == "INVALID_SIGNATURE":
        return False
    return None


def _load_signature_checker() -> Any:
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    import signature_checker
    return signature_checker


def _distribution_label(dist: importlib.metadata.Distribution) -> str:
    name = dist.metadata["Name"] if "Name" in dist.metadata else "unknown"
    return f"{name}=={dist.version}"


def _static_probe(
    signature_checker: Any,
    wheel_bytes: bytes,
    case: dict[str, Any],
) -> dict[str, Any]:
    call = case.get("static_call")
    if not isinstance(call, dict):
        return {
            "status": "NOT_APPLICABLE", "api_valid": None,
            "reason": "static_checker_has_no_matching_probe",
        }
    try:
        result = signature_checker.inspect_wheel_bytes(wheel_bytes, [call])
    except Exception as exc:
        return {
            "status": "INCONCLUSIVE", "api_valid": None,
            "reason": "static_checker_exception",
            "error_type": type(exc).__name__, "error": str(exc)[:1000],
        }
    status = result.get("status")
    return {
        "status": status, "api_valid": _static_api_valid(status),
        "reason": result.get("reason"),
        "unresolved_calls": result.get("unresolved_calls", []),
        "inspected_module_count": result.get("inspected_module_count"),
        "binary_extension_count": result.get("binary_extension_count"),
        "dynamic_getattr_modules": result.get("dynamic_getattr_modules", []),
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = [
        row for row in rows
        if type(row.get("api_valid")) is bool
        and type(row.get("static_api_valid")) is bool
    ]
    tp = sum(row["api_valid"] is True and row["static_api_valid"] is True for row in resolved)
    fp = sum(row["api_valid"] is False and row["static_api_valid"] is True for row in resolved)
    tn = sum(row["api_valid"] is False and row["static_api_valid"] is False for row in resolved)
    fn = sum(row["api_valid"] is True and row["static_api_valid"] is False for row in resolved)
    predicted_positive, actual_positive = tp + fp, tp + fn
    return {
        "interpretation": (
            "positive means the API is reachable at runtime; only cases with "
            "both runtime and static boolean results enter the confusion matrix"
        ),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "resolved_case_count": len(resolved), "total_case_count": len(rows),
        "coverage": len(resolved) / len(rows) if rows else None,
        "ground_truth_unknown_count": sum(row.get("api_valid") is None for row in rows),
        "static_inconclusive_count": sum(
            isinstance(row.get("static_result"), dict)
            and row["static_result"].get("status") == "INCONCLUSIVE"
            for row in rows
        ),
        "static_not_applicable_count": sum(
            isinstance(row.get("static_result"), dict)
            and row["static_result"].get("status") == "NOT_APPLICABLE"
            for row in rows
        ),
        "static_unknown_count": sum(
            row.get("static_api_valid") is None for row in rows
        ),
        "precision": tp / predicted_positive if predicted_positive else None,
        "recall": tp / actual_positive if actual_positive else None,
    }


def run_harness(wheelhouse: Path, manifest_path: Path, output_path: Path) -> dict[str, Any]:
    if not sys.platform.startswith("linux") or os.name != "posix":
        raise RuntimeError("Ground Truth probes require the Linux POSIX sandbox")
    if os.environ.get("JAMP_GROUND_TRUTH_SANDBOX") != "docker-network-none":
        raise RuntimeError("required Docker network-isolated sandbox marker is missing")
    if os.environ.get("JAMP_GROUND_TRUTH_NETWORK") != "none":
        raise RuntimeError("network isolation must be explicitly set to none")

    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "jamp.hunt.wheelhouse.v1"
    ):
        raise ValueError("unsupported wheelhouse manifest schema")
    _validate_target_metadata(manifest)
    wheel_paths = _validate_wheelhouse(wheelhouse, manifest)

    runtime_versions: dict[str, str] = {}
    wheel_bytes_by_package: dict[str, bytes] = {}
    for package, pin in TARGETS.items():
        wheel_path = wheel_paths[pin["filename"]]
        if sha256_file(wheel_path) != pin["sha256"]:
            raise ValueError(f"{package}: pinned target wheel SHA-256 mismatch")
        installed_version = importlib.metadata.version(package)
        if installed_version != pin["version"]:
            raise ValueError(
                f"{package}: installed version mismatch; "
                f"expected={pin['version']} observed={installed_version}"
            )
        runtime_versions[package] = installed_version
        wheel_bytes_by_package[package] = wheel_path.read_bytes()

    signature_checker = _load_signature_checker()
    results: list[dict[str, Any]] = []
    for case in CASE_DEFINITIONS:
        runtime = _run_runtime_probe(case)
        static = _static_probe(
            signature_checker, wheel_bytes_by_package[case["package"]], case
        )
        api_valid = runtime.get("api_valid")
        static_api_valid = static.get("api_valid")
        if type(api_valid) is not bool or type(static_api_valid) is not bool:
            outcome = "UNEVALUABLE"
        elif api_valid == static_api_valid:
            outcome = "MATCH"
        else:
            outcome = "MISMATCH"
        results.append({
            "case_id": case["case_id"], "package": case["package"],
            "package_version": runtime_versions[case["package"]],
            "description": case["description"],
            "probe": {key: value for key, value in case.items() if key != "static_call"},
            "api_valid": api_valid, "ground_truth_reason": runtime.get("reason"),
            "runtime_probe": runtime, "static_api_valid": static_api_valid,
            "static_result": static, "diagnostic_outcome": outcome,
        })

    metrics = _metrics(results)
    output: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "execution_status": "COMPLETED",
        "qualification_status": "NOT_GRANTED",
        "scope": {
            "classification": "DIAGNOSTIC_ONLY", "case_count": len(results),
            "main_100_case_benchmark_modified": False,
            "included_in_main_100_case_score": False,
            "api_valid_semantics": (
                "true/false only after successful runtime resolution; null means "
                "unknown or unevaluable and is excluded from TP/FP/TN/FN"
            ),
        },
        "source": {
            "wheel_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "targets": {
                package: {
                    "version": pin["version"], "filename": pin["filename"],
                    "sha256": pin["sha256"],
                }
                for package, pin in TARGETS.items()
            },
            "wheelhouse_count": manifest.get("wheelhouse_count"),
        },
        "environment": {
            "python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "machine": platform.machine(),
            "network_isolation": "Docker --network none (workflow-enforced)",
            "sandbox_image_id": os.environ.get("JAMP_SANDBOX_IMAGE_ID"),
            "resource_limits": {
                "container_memory": "1 GiB", "container_cpus": 1,
                "container_pids": 64, "probe_cpu_seconds": 10,
                "probe_address_space_bytes": 512 * 1024 * 1024,
                "probe_file_size_bytes": 1024 * 1024,
                "probe_open_files": 64, "probe_timeout_seconds": 12,
            },
            "installed_distributions": sorted(
                _distribution_label(dist)
                for dist in importlib.metadata.distributions()
            ),
        },
        "metrics": metrics, "cases": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_path)
    print(
        "GROUND_TRUTH_HARNESS_COMPLETED: "
        f"cases={len(results)} resolved={metrics['resolved_case_count']} "
        f"coverage={metrics['coverage']}", flush=True,
    )
    print(f"GROUND_TRUTH_JSON: {output_path}", flush=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_harness(args.wheelhouse, args.manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
