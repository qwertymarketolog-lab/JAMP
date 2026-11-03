"""Static-only wheel signature checks for The Hunt v0.3.

Wheel contents are read directly from an in-memory ZIP archive. No extraction,
installation, import, or execution of downloaded package code is performed.
"""
from __future__ import annotations

import ast
import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.request import Request, urlopen

from provenance_checker import fetch_pypi_json

MAX_WHEEL_BYTES = 25 * 1024 * 1024
MAX_SOURCE_BYTES = 10 * 1024 * 1024
TIMEOUT_SECONDS = 30
ImportAliases = dict[str, tuple[str, tuple[str, ...]]]
CallRecords = list[dict[str, Any]]
SymbolIndex = tuple[
    set[str],
    dict[str, set[str]],
    dict[str, dict[str, set[str]]],
    dict[str, dict[str, tuple[str, str]]],
    set[str],
]


def _dotted_name(node: ast.AST) -> tuple[str, list[str]] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return current.id, list(reversed(parts))


def _imports_and_calls(
    code_str: str, package_name: str
) -> tuple[ImportAliases, CallRecords, CallRecords]:
    tree = ast.parse(code_str)
    aliases: dict[str, tuple[str, tuple[str, ...]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                aliases[local_name] = (
                    alias.name if alias.asname else alias.name.split(".")[0],
                    (),
                )
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
        if re.sub(r"[-_.]+", "-", target[0].split(".")[0]).lower()
        == normalized_package
    }
    calls: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted_name(node.func)
        if dotted is not None:
            root, attributes = dotted
            if root in matching:
                base_module, prefix = matching[root]
                calls.append(
                    {
                        "module": base_module,
                        "symbol_path": list(prefix) + attributes,
                        "source_expression": ast.unparse(node.func),
                    }
                )
            continue

        # A package-originating call whose receiver is another call (or another
        # dynamic expression) cannot be resolved safely from static declarations.
        package_root_used = any(
            isinstance(child, ast.Name) and child.id in matching
            for child in ast.walk(node.func)
        )
        if package_root_used:
            unsupported.append(
                {
                    "source_expression": ast.unparse(node.func),
                    "reason": "dynamic_call_receiver_unresolved",
                }
            )
    return matching, calls, unsupported


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
    reexports: dict[str, dict[str, tuple[str, str]]] = {}
    dynamic_modules: set[str] = set()
    for path, source in sources.items():
        module = _module_name(path)
        if module is None:
            continue
        tree = ast.parse(source, filename=path)
        modules.add(module)
        functions[module] = set()
        classes[module] = {}
        reexports[module] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[module].add(node.name)
                if node.name == "__getattr__":
                    dynamic_modules.add(module)
            elif isinstance(node, ast.ClassDef):
                methods = {
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                classes[module][node.name] = methods
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    package = (
                        module
                        if path.endswith("/__init__.py")
                        else module.rpartition(".")[0]
                    )
                    package_parts = package.split(".") if package else []
                    if node.level > 1:
                        package_parts = package_parts[: -(node.level - 1)]
                    target_module = ".".join(
                        [*package_parts, *(node.module.split(".") if node.module else [])]
                    )
                else:
                    target_module = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    exported_name = alias.asname or alias.name
                    reexports[module][exported_name] = (target_module, alias.name)
    return modules, functions, classes, reexports, dynamic_modules


def _symbol_exists(
    base_module: str,
    symbol_path: list[str],
    modules: set[str],
    functions: dict[str, set[str]],
    classes: dict[str, dict[str, set[str]]],
    reexports: dict[str, dict[str, tuple[str, str]]],
) -> bool:
    if not symbol_path:
        return False

    def resolve(
        module_name: str,
        path: list[str],
        visited: set[tuple[str, tuple[str, ...]]],
    ) -> bool:
        key = (module_name, tuple(path))
        if key in visited:
            return False
        visited.add(key)
        for split in range(len(path)):
            candidate_module = ".".join([module_name, *path[:split]])
            remaining = path[split:]
            if candidate_module not in modules:
                continue
            if len(remaining) == 1 and (
                remaining[0] in functions.get(candidate_module, set())
                or remaining[0] in classes.get(candidate_module, {})
            ):
                return True
            if (
                len(remaining) == 2
                and remaining[0] in classes.get(candidate_module, {})
                and remaining[1] in classes[candidate_module][remaining[0]]
            ):
                return True
            exported = reexports.get(candidate_module, {}).get(remaining[0])
            if exported is not None:
                target_module, target_symbol = exported
                if target_module and resolve(
                    target_module, [target_symbol, *remaining[1:]], visited
                ):
                    return True
        return False

    return resolve(base_module, symbol_path, set())


def inspect_wheel_bytes(
    wheel_bytes: bytes,
    calls: list[dict[str, Any]],
    unsupported_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Inspect wheel source without extraction and resolve requested declarations."""
    if len(wheel_bytes) > MAX_WHEEL_BYTES:
        return {"status": "INCONCLUSIVE", "reason": "wheel_too_large"}
    if unsupported_calls:
        return {
            "status": "INCONCLUSIVE",
            "reason": "dynamic_call_receiver_unresolved",
            "unsupported_calls": unsupported_calls,
        }
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as archive:
            binary_members = [
                member.filename
                for member in archive.infolist()
                if not member.is_dir()
                and member.filename.lower().endswith((".so", ".pyd"))
            ]
        sources = read_wheel_sources(wheel_bytes)
        modules, functions, classes, reexports, dynamic_modules = _build_symbol_index(
            sources
        )
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile, SyntaxError):
        return {"status": "INCONCLUSIVE", "reason": "wheel_source_unreadable"}
    if not calls:
        return {
            "status": "INCONCLUSIVE",
            "reason": "no_package_calls",
            "inspected_module_count": len(modules),
        }
    unresolved = [
        call
        for call in calls
        if not _symbol_exists(
            call["module"],
            call["symbol_path"],
            modules,
            functions,
            classes,
            reexports,
        )
    ]
    if unresolved and dynamic_modules:
        status = "INCONCLUSIVE"
        reason = "dynamic_attribute_present"
    elif unresolved and binary_members:
        status = "INCONCLUSIVE"
        reason = "binary_extension_not_inspected"
    elif unresolved and any(
        call["symbol_path"]
        and call["symbol_path"][0] in reexports.get(call["module"], {})
        for call in unresolved
    ):
        status = "INCONCLUSIVE"
        reason = "unresolved_reexport"
    else:
        status = "INVALID_SIGNATURE" if unresolved else "EXISTS"
        reason = "symbol_missing" if unresolved else None
    return {
        "status": status,
        "reason": reason,
        "calls": calls,
        "unresolved_calls": unresolved,
        "unsupported_calls": [],
        "inspected_module_count": len(modules),
        "inspected_source_paths": sorted(sources),
        "binary_extension_count": len(binary_members),
        "dynamic_getattr_modules": sorted(dynamic_modules),
    }


def _parse_upload_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _latest_wheel(metadata: dict[str, Any]) -> dict[str, Any] | None:
    releases = metadata.get("releases")
    if not isinstance(releases, dict):
        return None
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for release_files in releases.values():
        if not isinstance(release_files, list):
            continue
        for item in release_files:
            if not isinstance(item, dict) or item.get("packagetype") != "bdist_wheel":
                continue
            timestamp = _parse_upload_time(
                item.get("upload_time_iso_8601") or item.get("upload_time")
            )
            if timestamp is not None:
                candidates.append((timestamp, item))
    if not candidates:
        return None
    return max(candidates, key=lambda pair: pair[0])[1]


def _download_wheel(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "JAMP-The-Hunt-v0.3"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = response.read(MAX_WHEEL_BYTES + 1)
    if len(payload) > MAX_WHEEL_BYTES:
        raise ValueError("wheel exceeds download limit")
    return payload


def check_signature(code_str: str, package_name: str) -> dict[str, Any]:
    """Check imported package calls against hash-verified latest PyPI wheel source."""
    try:
        aliases, calls, unsupported = _imports_and_calls(code_str, package_name)
    except (SyntaxError, ValueError, TypeError) as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": "generated_code_parse_failed",
            "error_type": type(exc).__name__,
        }
    if not aliases:
        return {"status": "INCONCLUSIVE", "reason": "package_import_not_found"}
    if unsupported:
        return {
            "status": "INCONCLUSIVE",
            "reason": "dynamic_call_receiver_unresolved",
            "unsupported_calls": unsupported,
            "calls": calls,
        }

    try:
        http_status, metadata = fetch_pypi_json(package_name)
        if http_status != 200 or not isinstance(metadata, dict):
            return {
                "status": "INCONCLUSIVE",
                "reason": "package_metadata_unavailable",
            }
        latest = _latest_wheel(metadata)
        if latest is None:
            return {"status": "INCONCLUSIVE", "reason": "wheel_not_found"}
        digests = latest.get("digests")
        expected_hash = digests.get("sha256") if isinstance(digests, dict) else None
        if (
            not isinstance(expected_hash, str)
            or len(expected_hash) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in expected_hash)
        ):
            return {"status": "INCONCLUSIVE", "reason": "wheel_hash_missing"}

        wheel_bytes = _download_wheel(latest["url"])
        actual_hash = hashlib.sha256(wheel_bytes).hexdigest()
        if actual_hash.lower() != expected_hash.lower():
            return {
                "status": "INCONCLUSIVE",
                "reason": "hash_mismatch",
                "expected_sha256": expected_hash.lower(),
                "actual_sha256": actual_hash,
                "wheel_filename": latest.get("filename"),
            }

        result = inspect_wheel_bytes(wheel_bytes, calls)
        result.update(
            {
                "package": package_name,
                "wheel_filename": latest.get("filename"),
                "wheel_url": latest["url"],
                "wheel_sha256_expected": expected_hash.lower(),
                "wheel_sha256_observed": actual_hash,
                "import_aliases": sorted(aliases),
            }
        )
        return result
    except Exception as exc:
        return {
            "status": "INCONCLUSIVE",
            "reason": "wheel_retrieval_or_inspection_failed",
            "error_type": type(exc).__name__,
        }
