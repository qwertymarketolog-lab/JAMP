"""P21.3 deterministic presentation, inspection, verification and lineage layer.

The module owns no scientific semantics and performs no I/O.  Callers inject
already-resolved immutable sessions and content-addressed object exports.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import defaultdict, deque
from typing import Any, Mapping, Sequence

from .session import ResearchSession

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_KINDS = ("question", "plan", "execution", "result", "interpretation", "claim", "consensus", "revision")
_RUNTIME_KEYS = {"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id", "runtime", "host", "platform"}


class CLIError(ValueError):
    """Deterministic user-facing CLI validation error."""


def _hash(value: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise CLIError("invalid content-addressed hash")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise CLIError("object is not canonically serializable") from exc


def _reject_runtime(value: Any) -> None:
    if isinstance(value, Mapping):
        if _RUNTIME_KEYS.intersection(value):
            raise CLIError("runtime metadata is forbidden")
        for item in value.values():
            _reject_runtime(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_runtime(item)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jamp")
    research = parser.add_subparsers(dest="group", required=True)
    research_parser = research.add_parser("research")
    commands = research_parser.add_subparsers(dest="command", required=True)
    session_parser = commands.add_parser("session")
    session_commands = session_parser.add_subparsers(dest="session_command", required=True)
    inspect = session_commands.add_parser("inspect")
    inspect.add_argument("session_hash")
    for name in ("lineage", "verify", "export"):
        command = commands.add_parser(name)
        command.add_argument("hash")
    return parser


class ResearchCLI:
    """Pure presentation facade over injected session/object mappings."""

    command_names = frozenset({"session", "lineage", "verify", "export"})
    source_semantics = frozenset()
    imports = frozenset({"jamp.research.session"})

    def __init__(self, sessions: Mapping[str, ResearchSession], objects: Mapping[str, Mapping[str, Any]]):
        self.sessions = dict(sessions)
        self.objects = {k: copy.deepcopy(dict(v)) for k, v in objects.items()}
        self._snapshots = {k: copy.deepcopy(v) for k, v in self.objects.items()}
        for key, value in self.objects.items():
            _hash(key)
            if not isinstance(value, Mapping):
                raise CLIError("artifact must be an object mapping")
            _reject_runtime(value)

    def _session(self, session_hash: str) -> ResearchSession:
        _hash(session_hash)
        try:
            session = self.sessions[session_hash]
        except KeyError as exc:
            raise CLIError("unknown session") from exc
        if not session.verify() or session.session_hash != session_hash:
            raise CLIError("invalid session identity")
        return session

    def inspect(self, session_hash: str) -> str:
        session = self._session(session_hash)
        payload = {
            "session_hash": session.session_hash,
            "metadata": session.metadata,
            "status": session.status,
            "indexes": session.indexes,
        }
        return _json(payload)

    def render_metadata(self, metadata: Mapping[str, Any]) -> str:
        _reject_runtime(metadata)
        return _json(metadata)

    def _object_hash(self, obj: Mapping[str, Any], fallback: str) -> str:
        for key in ("question_hash", "plan_hash", "execution_hash", "result_hash", "interpretation_hash", "claim_hash", "consensus_hash", "revision_hash"):
            if key in obj:
                value = obj[key]
                if value != fallback:
                    raise CLIError("artifact substitution detected")
                return value
        raise CLIError("artifact has no content-addressed identity")

    def _graph(self, target_hash: str) -> dict[str, set[str]]:
        _hash(target_hash)
        if target_hash not in self.objects:
            raise CLIError("unknown artifact")
        graph: dict[str, set[str]] = defaultdict(set)
        for key, obj in self.objects.items():
            _reject_runtime(obj)
            identity = self._object_hash(obj, key)
            graph.setdefault(identity, set())
            for field, value in obj.items():
                if field.endswith("_hash") and field != "artifact_hash":
                    if isinstance(value, str) and _HASH_RE.fullmatch(value):
                        if value in self.objects:
                            graph[identity].add(value)
                            graph[value].add(identity)
        return graph

    def _detect_cycle(self, graph: Mapping[str, set[str]]) -> None:
        directed: dict[str, set[str]] = defaultdict(set)
        for key, obj in self.objects.items():
            identity = self._object_hash(obj, key)
            for field, value in obj.items():
                if field.endswith("_hash") and field != "artifact_hash" and isinstance(value, str) and _HASH_RE.fullmatch(value) and value in self.objects:
                    directed[identity].add(value)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise CLIError("cycle detected")
            if node in visited:
                return
            visiting.add(node)
            for child in sorted(directed.get(node, ())):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in sorted(directed):
            visit(node)

    def lineage(self, artifact_hash: str) -> str:
        _hash(artifact_hash)
        graph = self._graph(artifact_hash)
        self._detect_cycle(graph)
        reachable: set[str] = set()
        queue = deque([artifact_hash])
        while queue:
            node = queue.popleft()
            if node in reachable:
                continue
            reachable.add(node)
            queue.extend(sorted(graph.get(node, ())))
        rank = {kind: i for i, kind in enumerate(_KINDS)}
        def kind_of(ref: str) -> str:
            return next((k for k in _KINDS if ref in self._refs_for_kind(k)), "unknown")
        ordered = sorted(reachable, key=lambda ref: (rank.get(kind_of(ref), 99), ref))
        return "\n".join(ordered)

    def _refs_for_kind(self, kind: str) -> tuple[str, ...]:
        refs = []
        suffix = f"{kind}_hash"
        for key, obj in self.objects.items():
            if obj.get(suffix) == key:
                refs.append(key)
        return tuple(sorted(refs))

    def verify(self, session_hash: str, *, require_objects: bool = False) -> bool:
        session = self._session(session_hash)
        for kind, refs in session.indexes.items():
            for ref in refs:
                if ref not in self.objects:
                    if require_objects:
                        raise CLIError("referenced artifact is missing")
                    continue
                obj = self.objects[ref]
                if obj != self._snapshots[ref]:
                    raise CLIError("artifact tamper detected")
                self._object_hash(obj, ref)
        if require_objects:
            self._detect_cycle(self._graph(next(iter((r for refs in session.indexes.values() for r in refs)), session.session_hash)))
        return True

    def export(self, session_hash: str) -> str:
        session = self._session(session_hash)
        return session.export()


def main(argv: Sequence[str] | None = None, *, cli: ResearchCLI | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if cli is None:
        raise CLIError("a resolver-backed ResearchCLI is required")
    if args.command == "session" and args.session_command == "inspect":
        print(cli.inspect(args.session_hash))
    elif args.command == "lineage":
        print(cli.lineage(args.hash))
    elif args.command == "verify":
        print(json.dumps({"verified": cli.verify(args.hash)}, sort_keys=True, separators=(",", ":")))
    elif args.command == "export":
        print(cli.export(args.hash))
    else:
        raise CLIError("unsupported command")
    return 0
