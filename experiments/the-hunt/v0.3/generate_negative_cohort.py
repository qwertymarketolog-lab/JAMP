"""Generate a reproducible static API-negative cohort from pinned wheel evidence.

No package is installed, imported, or executed. INVALID means the generated
attribute is absent from the exact wheel's inspectable Python source and the
target module has no dynamic attribute hook that could synthesize it.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

RECOVERY_ARTIFACT_ID = 13299716958
RECOVERY_ARTIFACT_SHA256 = "93cf36e696897bfca8ab99e500a8e625e8bae131d5944f56b1cb879ccdeae3b6"
WHEEL_MANIFEST_SHA256 = "5425ec5849201997ef7b6472ca64d909ea1165fc152064f120593a8fabbc4f6b"

PACKAGES = (
    "amqp", "anyio", "boto3", "celery", "click", "fastapi", "flask",
    "httpx", "jinja2", "kombu", "packaging", "pydantic", "redis",
    "requests", "sqlalchemy", "starlette", "urllib3", "werkzeug",
    "blinker", "certifi",
)
POSITIVE_CONTROLS = {
    "amqp": ("amqp.connection", "Connection", "from amqp.connection import Connection\nConnection()"),
    "anyio": ("anyio._core._eventloop", "run", "from anyio._core._eventloop import run\nrun()"),
    "boto3": ("boto3.session", "Session", "from boto3.session import Session\nSession()"),
    "celery": ("celery.app.base", "Celery", "from celery.app.base import Celery\nCelery()"),
    "click": ("click.decorators", "command", "from click.decorators import command\ncommand(lambda: None)"),
    "fastapi": ("fastapi.applications", "FastAPI", "from fastapi.applications import FastAPI\nFastAPI()"),
    "flask": ("flask.app", "Flask", "from flask.app import Flask\nFlask(__name__)"),
    "httpx": ("httpx._api", "get", "from httpx._api import get\nget('https://example.invalid')"),
    "jinja2": ("jinja2.environment", "Environment", "from jinja2.environment import Environment\nEnvironment()"),
    "kombu": ("kombu.connection", "Connection", "from kombu.connection import Connection\nConnection('amqp://')"),
    "packaging": ("packaging.version", "Version", "from packaging.version import Version\nVersion('1.0')"),
    "pydantic": ("pydantic.main", "BaseModel", "from pydantic.main import BaseModel\nBaseModel()"),
    "redis": ("redis.client", "Redis", "from redis.client import Redis\nRedis()"),
    "requests": ("requests.api", "get", "from requests.api import get\nget('https://example.invalid')"),
    "sqlalchemy": ("sqlalchemy.engine", "create_engine", "from sqlalchemy.engine import create_engine\ncreate_engine('sqlite://')"),
    "starlette": ("starlette.applications", "Starlette", "from starlette.applications import Starlette\nStarlette()"),
    "urllib3": ("urllib3.poolmanager", "PoolManager", "from urllib3.poolmanager import PoolManager\nPoolManager()"),
    "werkzeug": ("werkzeug.test", "Client", "from werkzeug.test import Client\nClient(None)"),
    "blinker": ("blinker.base", "Signal", "from blinker.base import Signal\nSignal()"),
    "certifi": ("certifi.core", "exit_cacert_ctx", "from certifi.core import exit_cacert_ctx\nexit_cacert_ctx()"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_member(source: Path, member: str) -> bytes:
    if source.is_dir():
        return (source / member).read_bytes()
    with zipfile.ZipFile(source) as archive:
        return archive.read(member)


def package_sources(wheel_bytes: bytes, package: str) -> dict[str, str]:
    sources: dict[str, str] = {}
    with zipfile.ZipFile(__import__("io").BytesIO(wheel_bytes)) as archive:
        for item in archive.infolist():
            name = item.filename
            if item.is_dir() or not name.endswith(".py"):
                continue
            if ".dist-info/" in name or ".data/" in name:
                continue
            sources[name] = archive.read(item).decode("utf-8")
    if f"{package}/__init__.py" not in sources:
        raise ValueError(f"{package}: no inspectable package root")
    return sources


def has_dynamic_attribute_hook(source: str) -> bool:
    tree = ast.parse(source)
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"__getattr__", "__getattribute__"}
        for node in tree.body
    )


def module_declares_symbol(sources: dict[str, str], module: str, symbol: str) -> bool:
    path = module.replace(".", "/") + ".py"
    source = sources.get(path)
    if source is None:
        path = module.replace(".", "/") + "/__init__.py"
        source = sources.get(path)
    if source is None:
        return False
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if any((alias.asname or alias.name) == symbol for alias in node.names):
                return True
    return False


def generate(recovery: Path, output: Path) -> dict[str, Any]:
    manifest_raw = read_member(recovery, "recovery-input/wheel_manifest.json")
    if sha256(manifest_raw) != WHEEL_MANIFEST_SHA256:
        raise ValueError("wheel manifest SHA-256 differs from pinned Recovery evidence")
    manifest = json.loads(manifest_raw)
    wheel_index = {
        norm(item["filename"].split("-", 1)[0]): item
        for item in manifest["wheels"]
    }
    negatives: list[dict[str, Any]] = []
    positives: list[dict[str, Any]] = []
    wheel_evidence: dict[str, dict[str, str]] = {}

    for package in PACKAGES:
        wheel = wheel_index.get(norm(package))
        if wheel is None:
            raise ValueError(f"pinned Recovery wheel missing for {package}")
        wheel_bytes = read_member(
            recovery, f"recovery-input/wheelhouse/{wheel['filename']}"
        )
        observed_digest = sha256(wheel_bytes)
        if observed_digest != wheel["sha256"]:
            raise ValueError(f"wheel SHA-256 mismatch for {package}")
        sources = package_sources(wheel_bytes, package)
        all_source = "\n".join(sources.values())

        target_module = None
        for source_path in sorted(sources):
            if not source_path.startswith(f"{package}/"):
                continue
            if source_path.endswith("/__init__.py"):
                module_name = source_path[:-12].replace("/", ".")
            else:
                module_name = source_path[:-3].replace("/", ".")
            if not module_name or module_name == package:
                continue
            if not has_dynamic_attribute_hook(sources[source_path]):
                target_module = module_name
                break
        if target_module is None:
            raise ValueError(f"{package}: no statically inspectable submodule")

        for index in range(1, 6):
            method = f"jamp_nonexistent_{package.replace('-', '_')}_{index:02d}"
            if re.search(rf"\b{re.escape(method)}\b", all_source):
                raise ValueError(f"synthetic method occurs in {package} wheel")
            negatives.append({
                "sample_id": f"neg-{package}-{index:02d}",
                "package_name": package,
                "target_module": target_module,
                "fake_method": method,
                "code_snippet": f"import {target_module} as jamp_target\njamp_target.{method}()",
                "ground_truth": "INVALID",
                "ground_truth_scope": "STATIC_MODULE_SOURCE_DECLARATION_ABSENCE",
                "ground_truth_evidence": {
                    "wheel_filename": wheel["filename"],
                    "wheel_sha256": observed_digest,
                    "python_source_file_count": len(sources),
                    "target_module": target_module,
                    "synthetic_identifier_absent_from_all_python_sources": True,
                    "target_module_dynamic_attribute_hook": False,
                },
            })

        positive_module, positive_symbol, positive_code = POSITIVE_CONTROLS[package]
        if not module_declares_symbol(sources, positive_module, positive_symbol):
            raise ValueError(
                f"positive control {positive_module}.{positive_symbol} lacks source declaration"
            )
        positives.append({
            "sample_id": f"pos-{package}-01",
            "package_name": package,
            "real_method": positive_symbol,
            "code_snippet": positive_code,
            "ground_truth": "VALID",
            "ground_truth_scope": "STATIC_MODULE_DECLARATION_OR_REEXPORT",
            "ground_truth_evidence": {
                "wheel_filename": wheel["filename"],
                "wheel_sha256": observed_digest,
                "module": positive_module,
                "symbol_declared_or_imported_in_module": True,
            },
        })
        wheel_evidence[package] = {
            "filename": wheel["filename"],
            "sha256": observed_digest,
        }

    report = {
        "schema_version": "jamp-hunt-api-negative-cohort-v0.1",
        "evaluation_mode": "PINNED_WHEEL_STATIC_SYNTHETIC_NEGATIVE",
        "ground_truth_contract": (
            "INVALID means absent from the exact wheel Python source and target module "
            "has no dynamic attribute hook; it is not a runtime-behavior claim."
        ),
        "recovery_artifact_id": 13299716958,
        "recovery_artifact_sha256": "93cf36e696897bfca8ab99e500a8e625e8bae131d5944f56b1cb879ccdeae3b6",
        "wheel_manifest_sha256": WHEEL_MANIFEST_SHA256,
        "wheel_count": manifest["wheel_count"],
        "package_count": len(PACKAGES),
        "negative_sample_count": len(negatives),
        "positive_control_count": len(positives),
        "generated_model_code_executed": False,
        "packages": wheel_evidence,
        "negative_samples": negatives,
        "positive_controls": positives,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = generate(args.recovery_artifact, args.output)
    print(json.dumps({
        "negative_sample_count": report["negative_sample_count"],
        "positive_control_count": report["positive_control_count"],
        "package_count": report["package_count"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
