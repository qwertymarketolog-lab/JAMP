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
DISTRIBUTION_IMPORT_ALIASES = {
    "beautifulsoup4": {"bs4"},
    "opencv-python": {"cv2"},
    "scikit-learn": {"sklearn"},
    "pillow": {"pil"},
    "pyyaml": {"yaml"},
    "python-dotenv": {"dotenv"},
}


def _normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()
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

    normalized_package = _normalized_distribution_name(package_name)
    expected_import_roots = {
        normalized_package,
        *(
            _normalized_distribution_name(name)
            for name in DISTRIBUTION_IMPORT_ALIASES.get(normalized_package, set())
        ),
    }
    matching = {
        alias: target
        for alias, target in aliases.items()
        if _normalized_distribution_name(target[0].split(".")[0])
        in expected_import_roots
    }
    calls: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    inherited_class_origins: dict[str, tuple[str, tuple[str, ...]]] = {}
    for class_node in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        for base in class_node.bases:
            base_expression = base.value if isinstance(base, ast.Subscript) else base
            dotted_base = _dotted_name(base_expression)
            if dotted_base is None:
                continue
            root, attributes = dotted_base
            if root not in matching:
                continue
            base_module, prefix = matching[root]
            inherited_class_origins[class_node.name] = (
                base_module,
                tuple([*prefix, *attributes]),
            )
            break
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
            elif isinstance(node.func, ast.Name) and node.func.id in inherited_class_origins:
                base_module, base_path = inherited_class_origins[node.func.id]
                calls.append(
                    {
                        "module": base_module,
                        "symbol_path": list(base_path),
                        "source_expression": ast.unparse(node.func),
                        "operation": "inherited_constructor",
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
    if not isinstance(payload, bytes):
        raise TypeError("wheel download did not return bytes")
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


# Export-resolution extension: literal star imports and Celery recreate_module.
# Static-only: wheel source is parsed in memory and never executed.

def _hunt_relative_import_target(
    module: str, path: str, node: ast.ImportFrom
) -> str:
    if not node.level:
        return node.module or ""
    package = module if path.endswith("/__init__.py") else module.rpartition(".")[0]
    parts = package.split(".") if package else []
    if node.level > 1:
        parts = parts[: -(node.level - 1)]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _hunt_statement_mutates_all(statement: ast.stmt) -> bool:
    """Return True when a module-level statement may change the __all__ binding."""
    pending: list[ast.AST] = [statement]
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.AugAssign) and (
            isinstance(node.target, ast.Name) and node.target.id == "__all__"
        ):
            return True
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Delete)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign)
                else node.targets
            )
            if any(
                (
                    isinstance(target, ast.Name) and target.id == "__all__"
                )
                or (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "__all__"
                )
                for target in targets
            ):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if (
                isinstance(receiver, ast.Name)
                and receiver.id == "__all__"
                and node.func.attr
                in {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"}
            ):
                return True
        pending.extend(ast.iter_child_nodes(node))
    return False


def _hunt_literal_all(tree: ast.Module) -> tuple[list[str] | None, bool]:
    """Return literal exports only when no later dynamic mutation can alter them."""
    names: list[str] | None = None
    declared = False
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in targets
            ):
                declared = True
                if node.value is None:
                    names = None
                    continue
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError, SyntaxError):
                    names = None
                    continue
                names = (
                    list(value)
                    if isinstance(value, (list, tuple))
                    and all(isinstance(item, str) for item in value)
                    else None
                )
                continue
        if _hunt_statement_mutates_all(node):
            declared = True
            names = None
    return names, declared


def _hunt_extended_index(
    sources: dict[str, str],
) -> tuple[
    set[str],
    dict[str, set[str]],
    dict[str, dict[str, set[str]]],
    dict[str, dict[str, tuple[str, str]]],
    set[str],
    dict[str, set[str]],
    dict[str, list[str] | None],
    set[str],
    dict[str, list[str]],
]:
    modules, functions, classes, reexports, dynamic_modules = _build_symbol_index(
        sources
    )
    module_bindings: dict[str, set[str]] = {}
    all_names: dict[str, list[str] | None] = {}
    all_declared: set[str] = set()
    dynamic_all: set[str] = set()
    star_imports: dict[str, list[str]] = {}
    imported_child_bindings: set[tuple[str, str]] = set()

    for path, source in sources.items():
        module = _module_name(path)
        if module is None:
            continue
        tree = ast.parse(source, filename=path)
        bindings: set[str] = set()
        star_imports[module] = []
        names, declared = _hunt_literal_all(tree)
        all_names[module] = names
        if declared:
            all_declared.add(module)
            if names is None:
                dynamic_all.add(module)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                bindings.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                target_module = _hunt_relative_import_target(module, path, node)
                if target_module in modules:
                    target_parts = target_module.split(".")
                    for index in range(1, len(target_parts)):
                        parent_module = ".".join(target_parts[:index])
                        child_module = ".".join(target_parts[: index + 1])
                        if parent_module in modules and child_module in modules:
                            imported_child_bindings.add(
                                (parent_module, target_parts[index])
                            )
                for alias in node.names:
                    if alias.name == "*":
                        star_imports[module].append(target_module)
                    else:
                        bindings.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bindings.add(alias.asname or alias.name.split(".")[0])
                    if alias.asname is None and alias.name.startswith(f"{module}."):
                        bindings.add(alias.name[len(module) + 1 :].split(".")[0])
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                assignment_targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                bindings.update(
                    target.id
                    for target in assignment_targets
                    if isinstance(target, ast.Name)
                )
        # Resolve literal lazy-export maps without executing package code.
        # Pydantic uses (__spec__.parent, ".main") to expose BaseModel.
        for statement in tree.body:
            assignment_value: ast.expr | None
            if isinstance(statement, ast.Assign):
                assignment_targets = statement.targets
                assignment_value = statement.value
            elif isinstance(statement, ast.AnnAssign):
                assignment_targets = [statement.target]
                assignment_value = statement.value
            else:
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "_dynamic_imports"
                for target in assignment_targets
            ) or not isinstance(assignment_value, ast.Dict):
                continue
            for key_node, value_node in zip(
                assignment_value.keys, assignment_value.values, strict=True
            ):
                if key_node is None:
                    continue
                try:
                    exported_name = ast.literal_eval(key_node)
                except (ValueError, TypeError, SyntaxError):
                    continue
                if (
                    not isinstance(exported_name, str)
                    or not isinstance(value_node, ast.Tuple)
                    or len(value_node.elts) != 2
                ):
                    continue
                package_expression, module_expression = value_node.elts
                try:
                    target_suffix = ast.literal_eval(module_expression)
                except (ValueError, TypeError, SyntaxError):
                    continue
                if not isinstance(target_suffix, str):
                    continue
                is_current_package = (
                    isinstance(package_expression, ast.Attribute)
                    and isinstance(package_expression.value, ast.Name)
                    and package_expression.value.id == "__spec__"
                    and package_expression.attr == "parent"
                )
                if is_current_package and target_suffix.startswith("."):
                    target_module = module + target_suffix
                elif is_current_package and target_suffix == "__module__":
                    continue
                else:
                    continue
                if target_module in modules:
                    reexports[module][exported_name] = (target_module, exported_name)

        module_bindings[module] = bindings

        for ast_node in ast.walk(tree):
            if not isinstance(ast_node, ast.Call):
                continue
            function = ast_node.func
            is_recreate = (
                isinstance(function, ast.Name) and function.id == "recreate_module"
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "recreate_module"
            )
            if not is_recreate:
                continue
            by_module = next(
                (keyword.value for keyword in ast_node.keywords if keyword.arg == "by_module"),
                None,
            )
            if by_module is None:
                dynamic_modules.add(module)
                continue
            try:
                mapping = ast.literal_eval(by_module)
            except (ValueError, TypeError, SyntaxError):
                dynamic_modules.add(module)
                continue
            if not isinstance(mapping, dict) or any(
                not isinstance(target_module, str)
                or not isinstance(symbols, (list, tuple))
                or not all(isinstance(symbol, str) for symbol in symbols)
                for target_module, symbols in mapping.items()
            ):
                dynamic_modules.add(module)
                continue
            for target_module, symbols in mapping.items():
                for symbol in symbols:
                    reexports[module][symbol] = (target_module, symbol)

    # Importing a child module through ImportFrom also binds that child as
    # an attribute on each package parent (for example, samplepkg.api).
    for parent_module, child_name in imported_child_bindings:
        module_bindings[parent_module].add(child_name)

    # Python star imports use literal __all__, or public top-level bindings
    # when __all__ is absent. A dynamic __all__ is deliberately unresolved.
    for importing_module, star_targets in star_imports.items():
        for star_target_module in star_targets:
            if star_target_module not in modules:
                dynamic_modules.add(importing_module)
                continue
            if star_target_module in dynamic_all:
                dynamic_modules.add(importing_module)
                continue
            if star_target_module in all_declared:
                exported_names = all_names[star_target_module] or []
            else:
                exported_names = sorted(
                    name
                    for name in module_bindings.get(star_target_module, set())
                    if not name.startswith("_")
                )
            for name in exported_names:
                reexports[importing_module][name] = (star_target_module, name)

    return (
        modules,
        functions,
        classes,
        reexports,
        dynamic_modules,
        module_bindings,
        all_names,
        all_declared | dynamic_all,
        star_imports,
    )


def _hunt_symbol_exists(
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


def _hunt_dynamic_resolution_relevant(
    base_module: str,
    symbol_path: list[str],
    modules: set[str],
    reexports: dict[str, dict[str, tuple[str, str]]],
    module_bindings: dict[str, set[str]],
    dynamic_modules: set[str],
) -> bool:
    """Return whether a missing symbol may be supplied by a relevant module hook.

    Traverse only symbol-specific static re-export edges. Unrelated imports and
    unrelated modules elsewhere in the distribution are deliberately ignored.
    """
    if not symbol_path:
        return False

    queue: list[tuple[str, tuple[str, ...]]] = [
        (base_module, tuple(symbol_path))
    ]
    visited: set[tuple[str, tuple[str, ...]]] = set()

    while queue:
        module_name, path = queue.pop(0)
        state = (module_name, path)
        if state in visited:
            continue
        visited.add(state)

        candidates: list[tuple[str, tuple[str, ...]]] = []
        for split in range(len(path)):
            candidate_module = ".".join([module_name, *path[:split]])
            remaining = path[split:]
            if candidate_module in modules and remaining:
                candidates.append((candidate_module, remaining))

        if not candidates:
            continue

        for candidate_module, remaining in candidates:
            # A child source file does not itself bind that child as an
            # attribute on its parent package. Only a static module binding
            # or re-export suppresses the parent's dynamic attribute hook.
            if (
                candidate_module in dynamic_modules
                and remaining[0]
                not in module_bindings.get(candidate_module, set())
            ):
                return True

            exported = reexports.get(candidate_module, {}).get(remaining[0])
            if exported is not None:
                target_module, target_symbol = exported
                if target_module:
                    queue.append(
                        (target_module, (target_symbol, *remaining[1:]))
                    )

    return False


def _hunt_binary_module_names(binary_members: list[str]) -> set[str]:
    """Map safe extension-wheel paths to importable module names."""
    modules: set[str] = set()
    for filename in binary_members:
        path = _safe_member_path(filename)
        if (
            path is None
            or any(part.endswith((".dist-info", ".data")) for part in path.parts)
        ):
            continue
        suffix = path.suffix.lower()
        if suffix not in {".so", ".pyd"}:
            continue
        stem = path.name[: -len(suffix)].split(".", 1)[0]
        if stem:
            modules.add(".".join([*path.parts[:-1], stem]))
    return modules


def _hunt_binary_resolution_relevant(
    base_module: str,
    symbol_path: list[str],
    modules: set[str],
    reexports: dict[str, dict[str, tuple[str, str]]],
    binary_modules: set[str],
    star_imports: dict[str, list[str]] | None = None,
) -> bool:
    """Return whether an extension module lies on this symbol's resolution path."""
    if not symbol_path:
        return False

    queue: list[tuple[str, tuple[str, ...]]] = [
        (base_module, tuple(symbol_path))
    ]
    visited: set[tuple[str, tuple[str, ...]]] = set()

    while queue:
        module_name, path = queue.pop(0)
        state = (module_name, path)
        if state in visited:
            continue
        visited.add(state)

        # Follow only explicit star-import edges from modules on this symbol path.
        for target_module in (star_imports or {}).get(module_name, []):
            queue.append((target_module, path))

        # Include the leaf: a binary submodule may itself be the requested symbol.
        for split in range(len(path) + 1):
            candidate_module = ".".join([module_name, *path[:split]])
            if candidate_module in binary_modules:
                return True
            if split == len(path) or candidate_module not in modules:
                continue
            exported = reexports.get(candidate_module, {}).get(path[split])
            if exported is not None:
                target_module, target_symbol = exported
                if target_module:
                    queue.append(
                        (target_module, (target_symbol, *path[split + 1 :]))
                    )
    return False


def inspect_wheel_bytes(
    wheel_bytes: bytes,
    calls: list[dict[str, Any]],
    unsupported_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Inspect wheel declarations, including literal star and lazy re-exports."""
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
        (
            modules,
            functions,
            classes,
            reexports,
            dynamic_modules,
            module_bindings,
            all_names,
            all_declared,
            star_imports,
        ) = _hunt_extended_index(sources)
        binary_modules = _hunt_binary_module_names(binary_members)
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        zipfile.BadZipFile,
        SyntaxError,
    ):
        return {"status": "INCONCLUSIVE", "reason": "wheel_source_unreadable"}
    if not calls:
        return {
            "status": "INCONCLUSIVE",
            "reason": "no_package_calls",
            "inspected_module_count": len(modules),
        }

    unresolved: list[dict[str, Any]] = []
    inconclusive_calls: list[dict[str, Any]] = []
    for call in calls:
        call_module = call.get("module")
        symbol_path = call.get("symbol_path")
        if not isinstance(call_module, str) or not isinstance(symbol_path, list):
            inconclusive_calls.append(call)
            continue
        if call.get("operation") == "star_import":
            if call_module not in modules or not symbol_path:
                unresolved.append(call)
                continue
            if call_module in all_declared and all_names.get(call_module) is None:
                inconclusive_calls.append(call)
                continue
            symbol = symbol_path[0]
            if call_module in all_declared:
                if symbol not in (all_names.get(call_module) or []):
                    unresolved.append(call)
                    continue
            elif symbol.startswith("_"):
                unresolved.append(call)
                continue
        if not _hunt_symbol_exists(
            call_module, symbol_path, modules, functions, classes, reexports
        ):
            if _hunt_dynamic_resolution_relevant(
                call_module,
                symbol_path,
                modules,
                reexports,
                module_bindings,
                dynamic_modules,
            ):
                inconclusive_calls.append(call)
            else:
                unresolved.append(call)

    reason: str | None = None
    if inconclusive_calls:
        status = "INCONCLUSIVE"
        reason = (
            "dynamic_star_import_exports"
            if any(call.get("operation") == "star_import" for call in inconclusive_calls)
            else "dynamic_attribute_present"
        )
    elif unresolved and any(
        _hunt_binary_resolution_relevant(
            call["module"],
            call["symbol_path"],
            modules,
            reexports,
            binary_modules,
            star_imports,
        )
        for call in unresolved
        if isinstance(call.get("module"), str)
        and isinstance(call.get("symbol_path"), list)
    ):
        status = "INCONCLUSIVE"
        reason = "binary_extension_not_inspected"
    elif unresolved and any(
        call.get("symbol_path")
        and call["symbol_path"][0] in reexports.get(call.get("module", ""), {})
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
        "inconclusive_calls": inconclusive_calls,
        "unsupported_calls": [],
        "inspected_module_count": len(modules),
        "inspected_source_paths": sorted(sources),
        "binary_extension_count": len(binary_members),
        "dynamic_getattr_modules": sorted(dynamic_modules),
    }
