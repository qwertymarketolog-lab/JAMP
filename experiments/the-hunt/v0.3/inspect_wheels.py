"""Inspect pinned PyPI wheels for top-level API and dynamic-export evidence.

This is an evidence collector, not an API-validity verdict. It records wheel
identity, static bindings, and dynamic-export indicators for human review.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

TARGETS: dict[str, tuple[str, str]] = {
    "httpx": (
        "1.0.dev6",
        "516cd76d86f016b2bc25d544d892a3ecce8db263459b3084894753fec322c841",
    ),
    "celery": (
        "5.7.0rc1",
        "e45c9f755fc6e86d9fedc89d4bc9e855fe43400eb9160e7c1fb878aed70959bd",
    ),
}
OUTPUT_DIR = Path("wheel-inspection-output")


def download_wheel(package: str, version: str) -> Path:
    destination = Path("/tmp/jamp-wheel-inspection") / package
    destination.mkdir(parents=True, exist_ok=True)
    print(f"\nDownloading {package}=={version}...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            "--no-deps",
            "--dest",
            str(destination),
            f"{package}=={version}",
        ],
        check=True,
    )
    wheels = sorted(destination.glob("*.whl"))
    if len(wheels) != 1:
        raise FileNotFoundError(
            f"Expected exactly one wheel for {package}=={version}; found {len(wheels)}"
        )
    return wheels[0]


def _literal_all(tree: ast.Module) -> tuple[list[str] | None, bool]:
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                value = node.value
                if value is None:
                    return None, True
                try:
                    parsed: Any = ast.literal_eval(value)
                except (ValueError, TypeError, SyntaxError):
                    return None, True
                if isinstance(parsed, (list, tuple)) and all(
                    isinstance(item, str) for item in parsed
                ):
                    return list(parsed), False
                return None, True
    return None, False


def _module_name(path: str) -> str:
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _import_target(module_name: str, path: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ""
    module_parts = module_name.split(".")
    package_parts = (
        module_parts if path.endswith("/__init__.py") else module_parts[:-1]
    )
    if node.level > 1:
        package_parts = package_parts[: -(node.level - 1)]
    target_parts = list(package_parts)
    if node.module:
        target_parts.extend(node.module.split("."))
    return ".".join(target_parts)


def _runtime_bindings(
    module: str,
    bindings: dict[str, set[str]],
    star_imports: dict[str, list[str]],
    all_names: dict[str, list[str] | None],
    all_declared: set[str],
    visited: set[str] | None = None,
) -> set[str]:
    visited = set() if visited is None else set(visited)
    if module in visited:
        return set()
    visited.add(module)
    names = set(bindings.get(module, set()))
    for target in star_imports.get(module, []):
        if target in all_declared:
            names.update(all_names.get(target) or [])
        else:
            names.update(
                name
                for name in _runtime_bindings(
                    target, bindings, star_imports, all_names, all_declared, visited
                )
                if not name.startswith("_")
            )
    return names


def analyze_wheel(
    package: str, wheel_path: Path, expected_sha256: str
) -> dict[str, object]:
    print(f"\n{'=' * 72}")
    print(f"ANALYZING: {wheel_path.name}")
    wheel_bytes = wheel_path.read_bytes()
    observed_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
    sha_matches = observed_sha256 == expected_sha256
    print(f"EXPECTED_SHA256: {expected_sha256}")
    print(f"OBSERVED_SHA256: {observed_sha256}")
    print(f"SHA256_MATCH: {sha_matches}")

    package_root = package.replace("-", "_") + "/"
    with zipfile.ZipFile(wheel_path) as archive:
        python_files = sorted(
            name
            for name in archive.namelist()
            if name.startswith(package_root) and name.endswith(".py")
        )
        init_path = package_root + "__init__.py"
        if init_path not in python_files:
            raise FileNotFoundError(f"Missing package initializer: {init_path}")

        init_tree = ast.parse(archive.read(init_path), filename=init_path)
        top_level_bindings: set[str] = set()
        top_level_imports: list[str] = []

        for node in init_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                top_level_bindings.add(node.name)
                print(f"INIT_DEF: {node.name}")
            elif isinstance(node, ast.ImportFrom):
                imported = [alias.asname or alias.name for alias in node.names]
                top_level_bindings.update(imported)
                top_level_imports.append(
                    f"from {node.module or '.'} import {', '.join(imported)}"
                )
                print(f"INIT_IMPORT: {top_level_imports[-1]}")
            elif isinstance(node, ast.Import):
                imported = [alias.asname or alias.name.split('.')[0] for alias in node.names]
                top_level_bindings.update(imported)
                top_level_imports.append(f"import {', '.join(imported)}")
                print(f"INIT_IMPORT: {top_level_imports[-1]}")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        top_level_bindings.add(target.id)

        all_names, all_dynamic = _literal_all(init_tree)
        module_getattr = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "__getattr__"
            for node in init_tree.body
        )

        type_checking_hits: list[str] = []
        getattr_hits: list[str] = []
        recreate_hits: list[str] = []
        recreate_mapping_hits: list[str] = []
        lazy_module_hits: list[str] = []
        celery_class_hits: list[str] = []
        get_definition_hits: list[str] = []
        get_import_hits: list[str] = []
        source_hits: list[str] = []
        parse_errors: list[str] = []
        module_bindings: dict[str, set[str]] = {}
        module_star_imports: dict[str, list[str]] = {}
        module_all_names: dict[str, list[str] | None] = {}
        modules_with_all: set[str] = set()

        for name in python_files:
            raw = archive.read(name)
            source = raw.decode("utf-8", errors="replace")
            try:
                tree = ast.parse(source, filename=name)
            except SyntaxError as error:
                parse_errors.append(f"{name}:{error.lineno}:{error.msg}")
                continue

            module = _module_name(name)
            module_bindings[module] = set()
            module_star_imports[module] = []
            literal_names, dynamic_all = _literal_all(tree)
            module_all_names[module] = literal_names
            if literal_names is not None or dynamic_all:
                modules_with_all.add(module)

            for top_node in tree.body:
                if isinstance(
                    top_node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                ):
                    module_bindings[module].add(top_node.name)
                    if top_node.name == "get":
                        get_definition_hits.append(f"{name}:{top_node.lineno}")
                elif isinstance(top_node, ast.ImportFrom):
                    target_module = _import_target(module, name, top_node)
                    for alias in top_node.names:
                        if alias.name == "*":
                            module_star_imports[module].append(target_module)
                        else:
                            bound_name = alias.asname or alias.name
                            module_bindings[module].add(bound_name)
                            if bound_name == "get":
                                get_import_hits.append(f"{name}:{top_node.lineno}")
                elif isinstance(top_node, ast.Import):
                    for alias in top_node.names:
                        bound_name = alias.asname or alias.name.split(".")[0]
                        module_bindings[module].add(bound_name)
                elif isinstance(top_node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        top_node.targets
                        if isinstance(top_node, ast.Assign)
                        else [top_node.target]
                    )
                    for target in targets:
                        if isinstance(target, ast.Name):
                            module_bindings[module].add(target.id)

            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
                    type_checking_hits.append(name)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == "__getattr__":
                        getattr_hits.append(name)
                if isinstance(node, ast.Call):
                    function = node.func
                    if (
                        isinstance(function, ast.Name)
                        and function.id == "recreate_module"
                    ) or (
                        isinstance(function, ast.Attribute)
                        and function.attr == "recreate_module"
                    ):
                        recreate_hits.append(name)
                        for keyword in node.keywords:
                            if keyword.arg == "by_module":
                                try:
                                    mapping: Any = ast.literal_eval(keyword.value)
                                except (ValueError, TypeError, SyntaxError):
                                    recreate_mapping_hits.append(
                                        f"{name}:{node.lineno}: by_module is nonliteral"
                                    )
                                else:
                                    if isinstance(mapping, dict):
                                        for module_name, symbols in mapping.items():
                                            if (
                                                module_name == "celery.app"
                                                or (
                                                    isinstance(symbols, (list, tuple))
                                                    and "Celery" in symbols
                                                )
                                            ):
                                                recreate_mapping_hits.append(
                                                    f"{name}:{node.lineno}: "
                                                    f"{module_name} -> {symbols}"
                                                )
                if isinstance(node, ast.ClassDef):
                    if node.name == "LazyModule":
                        lazy_module_hits.append(name)
                    if node.name == "Celery":
                        celery_class_hits.append(name)

            for line_number, line in enumerate(source.splitlines(), start=1):
                if any(
                    marker in line
                    for marker in (
                        "TYPE_CHECKING",
                        "__getattr__",
                        "recreate_module",
                        "by_module",
                        "class LazyModule",
                        "class Celery",
                        "def get(",
                        "__all__",
                    )
                ):
                    source_hits.append(f"{name}:{line_number}: {line.strip()}")

        package_module = package.replace("-", "_")
        runtime_package_bindings = _runtime_bindings(
            package_module,
            module_bindings,
            module_star_imports,
            module_all_names,
            modules_with_all,
        )
        report: dict[str, object] = {
            "package": package,
            "wheel_filename": wheel_path.name,
            "expected_sha256": expected_sha256,
            "observed_sha256": observed_sha256,
            "sha256_matches": sha_matches,
            "python_source_file_count": len(python_files),
            "python_source_files": python_files,
            "top_level_bindings": sorted(top_level_bindings),
            "top_level_imports": top_level_imports,
            "literal_all": all_names,
            "all_is_dynamic_or_nonliteral": all_dynamic,
            "httpx_top_level_get_binding": "get" in top_level_bindings,
            "httpx_get_listed_in_all": all_names is not None and "get" in all_names,
            "httpx_runtime_static_bindings": sorted(runtime_package_bindings),
            "httpx_get_attribute_static_binding": "get" in runtime_package_bindings,
            "get_definition_locations": sorted(set(get_definition_hits)),
            "get_import_locations": sorted(set(get_import_hits)),
            "package_level_getattr_in_init": module_getattr,
            "getattr_source_files": sorted(set(getattr_hits)),
            "type_checking_source_files": sorted(set(type_checking_hits)),
            "recreate_module_source_files": sorted(set(recreate_hits)),
            "recreate_module_by_module_exports": sorted(set(recreate_mapping_hits)),
            "lazy_module_class_source_files": sorted(set(lazy_module_hits)),
            "celery_class_source_files": sorted(set(celery_class_hits)),
            "source_evidence_lines": source_hits,
            "ast_parse_errors": parse_errors,
        }

    print("\nSTATIC EXPORT EVIDENCE:")
    print(f"TOP_LEVEL_GET_BINDING: {report['httpx_top_level_get_binding']}")
    print(f"TOP_LEVEL_CELERY_BINDING: {'Celery' in top_level_bindings}")
    print(f"HTTPX_GET_ATTRIBUTE_STATIC_BINDING: {report['httpx_get_attribute_static_binding']}")
    print(f"GET_DEFINITION_LOCATIONS: {report['get_definition_locations']}")
    print(f"GET_IMPORT_LOCATIONS: {report['get_import_locations']}")
    print(f"LITERAL_ALL: {all_names}")
    print(f"ALL_DYNAMIC_OR_NONLITERAL: {all_dynamic}")
    print(f"PACKAGE_LEVEL_GETATTR_IN_INIT: {module_getattr}")
    print("\nDYNAMIC / TYPE_CHECKING EVIDENCE:")
    for key in (
        "type_checking_source_files",
        "getattr_source_files",
        "recreate_module_source_files",
        "recreate_module_by_module_exports",
        "lazy_module_class_source_files",
        "celery_class_source_files",
    ):
        print(f"{key.upper()}: {report[key]}")
    print("\nSOURCE EVIDENCE LINES:")
    for line in source_hits:
        print(line)
    if parse_errors:
        print("\nAST_PARSE_ERRORS:")
        for error in parse_errors:
            print(error)
    return report


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    failed = False

    for package, (version, expected_sha256) in TARGETS.items():
        try:
            wheel = download_wheel(package, version)
            report = analyze_wheel(package, wheel, expected_sha256)
            reports.append(report)
            if not report["sha256_matches"] or report["ast_parse_errors"]:
                failed = True
        except Exception as error:  # retain a per-target failure in the evidence
            failed = True
            failure = {
                "package": package,
                "version": version,
                "error_type": type(error).__name__,
                "error": str(error),
            }
            reports.append(failure)
            print(f"FAILED_TO_ANALYZE: {json.dumps(failure, sort_keys=True)}")

    output_path = OUTPUT_DIR / "inspection.json"
    output_path.write_text(
        json.dumps(reports, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nINSPECTION_JSON: {output_path}")
    print(f"ALL_TARGETS_SHA_AND_AST_OK: {not failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
