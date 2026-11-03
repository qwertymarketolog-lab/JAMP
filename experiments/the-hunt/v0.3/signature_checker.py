"""Static-only wheel signature checks for The Hunt v0.3.

Wheel contents are read directly from an in-memory ZIP archive. No extraction,
installation, import, or execution of downloaded package code is performed.
"""
from __future__ import annotations

import ast
import io
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any
from urllib.request import Request, urlopen

from provenance_checker import fetch_pypi_json

MAX_WHEEL_BYTES = 25 * 1024 * 1024
MAX_SOURCE_BYTES = 10 * 1024 * 1024
TIMEOUT_SECONDS = 30
ImportAliases = dict[str, tuple[str, tuple[str, ...]]]
CallRecords = list[dict[str, Any]]
SymbolIndex = tuple[set[str], dict[str, set[str]], dict[str, dict[str, set[str]]]]


def _dotted_name(node: ast.AST) -> tuple[str, list[str]] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return current.id, list(reversed(parts))


def _imports_and_calls(code_str: str, package_name: str) -> tuple[ImportAliases, CallRecords]:
    tree = ast.parse(code_str)
    aliases: dict[str, tuple[str, tuple[str, ...]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                aliases[local_name] = (alias.name if alias.asname else alias.name.split(".")[0], ())
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                aliases[local_name] = (node.module, (alias.name,))

    normalized_package = re.sub(r"[-_.]+", "-", package_name).lower()
    matching = {
        alias: target
        for alias, target in aliases.items()
        if re.sub(r"[-_.]+", "-", target[0].split(".")[0]).lower() == normalized_package
    }
    calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        if dotted is None:
            continue
        root, attributes = dotted
        if root not in matching:
            continue
        base_module, prefix = matching[root]
        calls.append(
            {
                "module": base_module,
                "symbol_path": list(prefix) + attributes,
                "source_expression": ast.unparse(node.func),
            }
        )
    return matching, calls


def _safe_member_path(filename: str) -> PurePosixPath | None:
    if "\\" in filename:
        return None
    path = PurePosixPath(filename)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return None
    return path


def read_wheel_sources(wheel_bytes: bytes) -> dict[str, str]:
    """Read safe .py members in memory; never write archive paths to disk."""
    sources: dict[str, str] = {}
    total_source_bytes = 0
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as archive:
        for member in archive.infolist():
            path = _safe_member_path(member.filename)
            if path is None or member.is_dir() or path.suffix != ".py":
                continue
            if ".dist-info" in path.parts or ".data" in path.parts:
                continue
            if (
                member.file_size > MAX_SOURCE_BYTES
                or total_source_bytes + member.file_size > MAX_SOURCE_BYTES
            ):
                raise ValueError("wheel source exceeds inspection limit")
            content = archive.read(member)
            total_source_bytes += len(content)
            sources[path.as_posix()] = content.decode("utf-8")
    return sources


def _module_name(path: str) -> str | None:
    parts = list(PurePosixPath(path).parts)
    if not parts or parts[0].endswith((".dist-info", ".data")):
        return None
    if parts[-1] == "__init__.py":
        parts.pop()
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts) if parts else None


def _build_symbol_index(sources: dict[str, str]) -> SymbolIndex:
    modules: set[str] = set()
    functions: dict[str, set[str]] = {}
    classes: dict[str, dict[str, set[str]]] = {}
    for path, source in sources.items():
        module = _module_name(path)
        if module is None:
            continue
        tree = ast.parse(source, filename=path)
        modules.add(module)
        functions[module] = set()
        classes[module] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[module].add(node.name)
            elif isinstance(node, ast.ClassDef):
                methods = {
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                classes[module][node.name] = methods
    return modules, functions, classes


def _symbol_exists(
    base_module: str,
    symbol_path: list[str],
    modules: set[str],
    functions: dict[str, set[str]],
    classes: dict[str, dict[str, set[str]]],
) -> bool:
    if not symbol_path:
        return False
    for split in range(len(symbol_path)):
        module = ".".join([base_module, *symbol_path[:split]])
        symbol = symbol_path[split:]
        if module not in modules:
            continue
        if len(symbol) == 1 and (
            symbol[0] in functions.get(module, set())
            or symbol[0] in classes.get(module, {})
        ):
            return True
        if len(symbol) == 2 and symbol[0] in classes.get(module, {}):
            if symbol[1] in classes[module][symbol[0]]:
                return True
    return False


def inspect_wheel_bytes(wheel_bytes: bytes, calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Inspect wheel source without extraction and resolve requested declarations."""
    if len(wheel_bytes) > MAX_WHEEL_BYTES:
        return {"status": "INCONCLUSIVE", "reason": "wheel_too_large"}
    try:
        sources = read_wheel_sources(wheel_bytes)
        modules, functions, classes = _build_symbol_index(sources)
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile, SyntaxError):
        return {"status": "INCONCLUSIVE", "reason": "wheel_source_unreadable"}
    if not calls:
        return {
            "status": "INCONCLUSIVE",
            "reason": "no_package_calls",
            "inspected_module_count": len(modules),
        }
    unresolved = [
        call for call in calls
        if not _symbol_exists(
            call["module"], call["symbol_path"], modules, functions, classes
        )
    ]
    return {
        "status": "INVALID_SIGNATURE" if unresolved else "EXISTS",
        "reason": "symbol_missing" if unresolved else None,
        "calls": calls,
        "unresolved_calls": unresolved,
        "inspected_module_count": len(modules),
        "inspected_source_paths": sorted(sources),
    }


def _download_wheel(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "JAMP-The-Hunt-v0.3"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = response.read(MAX_WHEEL_BYTES + 1)
    if len(payload) > MAX_WHEEL_BYTES:
        raise ValueError("wheel exceeds download limit")
    return payload


def check_signature(code_str: str, package_name: str) -> dict[str, Any]:
    """Check imported package calls against declarations in the latest PyPI wheel."""
    try:
        aliases, calls = _imports_and_calls(code_str, package_name)
    except (SyntaxError, ValueError, TypeError) as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": "generated_code_parse_failed",
            "error_type": type(exc).__name__,
        }
    if not aliases:
        return {"status": "INCONCLUSIVE", "reason": "package_import_not_found"}

    try:
        http_status, metadata = fetch_pypi_json(package_name)
        if http_status != 200 or not isinstance(metadata, dict):
            return {"status": "INCONCLUSIVE", "reason": "package_metadata_unavailable"}
        files = metadata.get("urls")
        wheels = [
            item for item in files
            if isinstance(item, dict)
            and item.get("packagetype") == "bdist_wheel"
            and isinstance(item.get("url"), str)
        ] if isinstance(files, list) else []
        if not wheels:
            return {"status": "INCONCLUSIVE", "reason": "wheel_not_found"}
        latest = max(
            wheels,
            key=lambda item: item.get("upload_time_iso_8601")
            or item.get("upload_time")
            or "",
        )
        wheel_bytes = _download_wheel(latest["url"])
        result = inspect_wheel_bytes(wheel_bytes, calls)
        result["package"] = package_name
        result["wheel_filename"] = latest.get("filename")
        result["wheel_url"] = latest["url"]
        result["import_aliases"] = sorted(aliases)
        return result
    except Exception as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": "wheel_retrieval_or_inspection_failed",
            "error_type": type(exc).__name__,
        }
