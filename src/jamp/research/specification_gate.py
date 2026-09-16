"""N4 deterministic, fail-closed Specification Gate implementation.

The gate is strictly pre-execution. ``run_gate`` accepts only a SpecificationRef;
Raw Evidence, execution results, classifications, and verdicts are not part of
its callable interface or internal state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

from .canonical import canonical_bytes

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_SPEC = ("spec_id", "spec_version", "hypothesis_ref", "prediction_ref", "criterion_set_ref", "spec_hash", "frozen_at")
_REQUIRED_CRITERION = (
    "criterion_id", "criterion_version", "hypothesis_ref", "prediction_ref", "preconditions",
    "observation_schema", "acceptance_predicate", "rejection_predicate", "inconclusive_predicate",
    "self_test", "provenance_reference",
)
_ERROR_CODES = frozenset({
    "MISSING_REQUIRED_FIELD", "SCHEMA_VIOLATION", "UNRESOLVED_REFERENCE", "HASH_MISMATCH",
    "VERSION_MISMATCH", "EMPTY_CRITERION_SET", "MISSING_PREDICATE", "MISSING_SELF_TEST",
    "SELF_TEST_FAILURE", "SELF_TEST_AMBIGUITY", "NONDETERMINISTIC_EVALUATION",
    "PREDICATE_OVERLAP", "INCOMPLETE_COVERAGE", "UNRESOLVED_STATE", "FREEZE_BOUNDARY_VIOLATION",
})
_RESULTS = ("PASS", "FAIL", "INCONCLUSIVE")


class GateError(ValueError):
    """Base Specification Gate error."""


class GateStatus(str, Enum):
    PASS = "GATE_PASS"
    FAIL = "GATE_FAIL"


@dataclass(frozen=True, slots=True)
class SpecificationRef:
    spec_id: str
    spec_version: str
    spec_hash: str


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    artifact_ref: str
    requirement: str
    description: str


@dataclass(frozen=True, slots=True)
class GateResult:
    status: GateStatus
    spec_ref: SpecificationRef
    validated_hashes: tuple[str, ...]
    diagnostics: tuple[Diagnostic, ...]
    gate_contract_version: str = "v0"


class ArtifactSource(Protocol):
    """Read-only source of frozen specification-layer artifacts."""

    def get_specification(self, spec_hash: str) -> Mapping[str, Any]: ...
    def get_criterion_set(self, criterion_set_hash: str) -> Mapping[str, Any]: ...
    def get_criterion(self, criterion_hash: str) -> Mapping[str, Any]: ...
    def get_aggregation_rule(self, rule_hash: str) -> Mapping[str, Any]: ...


class MappingArtifactSource:
    """Deterministic in-memory artifact source used by the gate and its tests."""

    def __init__(
        self,
        *,
        specifications: Mapping[str, Mapping[str, Any]],
        criterion_sets: Mapping[str, Mapping[str, Any]],
        criteria: Mapping[str, Mapping[str, Any]],
        aggregation_rules: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self._specifications = dict(specifications)
        self._criterion_sets = dict(criterion_sets)
        self._criteria = dict(criteria)
        self._aggregation_rules = dict(aggregation_rules)

    def get_specification(self, spec_hash: str) -> Mapping[str, Any]:
        return self._specifications[spec_hash]

    def get_criterion_set(self, criterion_set_hash: str) -> Mapping[str, Any]:
        return self._criterion_sets[criterion_set_hash]

    def get_criterion(self, criterion_hash: str) -> Mapping[str, Any]:
        return self._criteria[criterion_hash]

    def get_aggregation_rule(self, rule_hash: str) -> Mapping[str, Any]:
        return self._aggregation_rules[rule_hash]


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(_HASH_RE.fullmatch(value))


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _content_hash(artifact: Mapping[str, Any], hash_field: str) -> str:
    payload = {k: _canonical(v) for k, v in artifact.items() if k != hash_field}
    return _hash(payload)


def _diagnostic(code: str, ref: str, requirement: str, description: str) -> Diagnostic:
    if code not in _ERROR_CODES:
        raise GateError(f"unknown diagnostic code: {code}")
    return Diagnostic(code, ref, requirement, description)


def _predicate_matches(predicate: Any, sample: Mapping[str, Any]) -> bool:
    """Evaluate the small deterministic predicate DSL defined for Gate v0 controls."""
    if not isinstance(predicate, Mapping):
        raise GateError("predicate must be a mapping")
    field = predicate.get("field")
    op = predicate.get("op")
    if not isinstance(field, str) or op not in {"eq", "ne", "lt", "le", "gt", "ge", "in", "not_in"}:
        raise GateError("unsupported predicate expression")
    actual = sample.get(field)
    expected = predicate.get("value")
    if op == "eq": return actual == expected
    if op == "ne": return actual != expected
    if op == "lt": return actual < expected
    if op == "le": return actual <= expected
    if op == "gt": return actual > expected
    if op == "ge": return actual >= expected
    if op == "in": return actual in expected
    return actual not in expected


def _predicate_vector(criterion: Mapping[str, Any], sample: Mapping[str, Any]) -> tuple[str, ...]:
    predicates = {
        "PASS": criterion["acceptance_predicate"],
        "FAIL": criterion["rejection_predicate"],
        "INCONCLUSIVE": criterion["inconclusive_predicate"],
    }
    return tuple(name for name, predicate in predicates.items() if _predicate_matches(predicate, sample))


class SpecificationGate:
    """Fail-closed pre-execution validator with no experimental-data input."""

    __slots__ = ("_source",)

    def __init__(self, source: ArtifactSource) -> None:
        self._source = source

    def validate_specification(self, spec_ref: SpecificationRef) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        try:
            spec = self._source.get_specification(spec_ref.spec_hash)
        except Exception:
            return (_diagnostic("UNRESOLVED_REFERENCE", spec_ref.spec_hash, "SpecificationRef", "specification reference does not resolve"),)
        missing = [key for key in _REQUIRED_SPEC if key not in spec]
        if missing:
            diagnostics.append(_diagnostic("MISSING_REQUIRED_FIELD", spec_ref.spec_hash, "Specification Schema v0", f"missing fields: {', '.join(missing)}"))
            return tuple(diagnostics)
        if (spec.get("spec_id"), spec.get("spec_version"), spec.get("spec_hash")) != (spec_ref.spec_id, spec_ref.spec_version, spec_ref.spec_hash):
            diagnostics.append(_diagnostic("VERSION_MISMATCH", spec_ref.spec_hash, "SpecificationRef", "reference does not match frozen specification identity"))
        if not _valid_hash(spec.get("spec_hash")) or _content_hash(spec, "spec_hash") != spec.get("spec_hash"):
            diagnostics.append(_diagnostic("HASH_MISMATCH", spec_ref.spec_hash, "spec_hash", "declared specification hash does not match canonical content"))
        if spec.get("frozen_at") is None:
            diagnostics.append(_diagnostic("FREEZE_BOUNDARY_VIOLATION", spec_ref.spec_hash, "frozen_at", "execution requires a frozen specification"))
        return tuple(diagnostics)

    def validate_referential_integrity(self, spec_ref: SpecificationRef) -> tuple[Diagnostic, ...]:
        diagnostics = list(self.validate_specification(spec_ref))
        if diagnostics:
            return tuple(diagnostics)
        spec = self._source.get_specification(spec_ref.spec_hash)
        criterion_set_hash = spec["criterion_set_ref"]
        if not _valid_hash(criterion_set_hash):
            return (_diagnostic("SCHEMA_VIOLATION", criterion_set_hash, "criterion_set_ref", "criterion_set_ref must be an immutable SHA-256 HashLink"),)
        try:
            criterion_set = self._source.get_criterion_set(criterion_set_hash)
        except Exception:
            return (_diagnostic("UNRESOLVED_REFERENCE", criterion_set_hash, "Criterion Set", "criterion set reference does not resolve"),)
        if criterion_set.get("criterion_set_hash") != criterion_set_hash or _content_hash(criterion_set, "criterion_set_hash") != criterion_set_hash:
            diagnostics.append(_diagnostic("HASH_MISMATCH", criterion_set_hash, "criterion_set_hash", "criterion set identity does not match canonical content"))
        criteria = criterion_set.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            diagnostics.append(_diagnostic("EMPTY_CRITERION_SET", criterion_set_hash, "criteria", "criterion set must contain at least one criterion"))
        if not _valid_hash(criterion_set.get("aggregation_rule_ref")):
            diagnostics.append(_diagnostic("SCHEMA_VIOLATION", criterion_set_hash, "aggregation_rule_ref", "aggregation rule must be an immutable SHA-256 HashLink"))
        else:
            try:
                rule = self._source.get_aggregation_rule(criterion_set["aggregation_rule_ref"])
                if _content_hash(rule, "aggregation_rule_hash") != criterion_set["aggregation_rule_ref"]:
                    diagnostics.append(_diagnostic("HASH_MISMATCH", criterion_set["aggregation_rule_ref"], "aggregation_rule_ref", "aggregation rule hash mismatch"))
            except Exception:
                diagnostics.append(_diagnostic("UNRESOLVED_REFERENCE", criterion_set["aggregation_rule_ref"], "Aggregation Rule", "aggregation rule reference does not resolve"))
        for ref in criteria or ():
            if not _valid_hash(ref):
                diagnostics.append(_diagnostic("SCHEMA_VIOLATION", str(ref), "criteria", "criterion reference must be an immutable SHA-256 HashLink"))
                continue
            try:
                criterion = self._source.get_criterion(ref)
            except Exception:
                diagnostics.append(_diagnostic("UNRESOLVED_REFERENCE", ref, "Criterion", "criterion reference does not resolve"))
                continue
            if _content_hash(criterion, "criterion_hash") != ref or criterion.get("criterion_hash") != ref:
                diagnostics.append(_diagnostic("HASH_MISMATCH", ref, "criterion_hash", "criterion hash mismatch"))
        return tuple(diagnostics)

    def run_criterion_self_tests(self, criterion_set_ref: str) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        try:
            criterion_set = self._source.get_criterion_set(criterion_set_ref)
        except Exception:
            return (_diagnostic("UNRESOLVED_REFERENCE", criterion_set_ref, "Criterion Set", "criterion set reference does not resolve"),)
        for ref in criterion_set.get("criteria", ()):
            try:
                criterion = self._source.get_criterion(ref)
            except Exception:
                diagnostics.append(_diagnostic("UNRESOLVED_REFERENCE", str(ref), "Criterion", "criterion reference does not resolve"))
                continue
            self_test = criterion.get("self_test")
            if not isinstance(self_test, Mapping) or any(k not in self_test for k in ("pass_case", "fail_case", "inconclusive_case")):
                diagnostics.append(_diagnostic("MISSING_SELF_TEST", ref, "self_test", "all three deterministic self-test cases are required"))
                continue
            for expected in _RESULTS:
                case = self_test[f"{expected.lower()}_case"]
                if not isinstance(case, Mapping) or "sample" not in case or "expected" not in case:
                    diagnostics.append(_diagnostic("MISSING_SELF_TEST", ref, "self_test", f"invalid {expected} control case"))
                    continue
                try:
                    vector = _predicate_vector(criterion, case["sample"])
                except Exception:
                    diagnostics.append(_diagnostic("NONDETERMINISTIC_EVALUATION", ref, "self_test", f"predicate evaluation failed for {expected} control case"))
                    continue
                if vector != (expected,):
                    diagnostics.append(_diagnostic("SELF_TEST_FAILURE", ref, "self_test", f"expected exactly {expected}, observed {vector or 'NO MATCH'}"))
        return tuple(diagnostics)

    def verify_predicate_coverage(self, criterion_set_ref: str) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        try:
            criterion_set = self._source.get_criterion_set(criterion_set_ref)
        except Exception:
            return (_diagnostic("UNRESOLVED_REFERENCE", criterion_set_ref, "Criterion Set", "criterion set reference does not resolve"),)
        for ref in criterion_set.get("criteria", ()):
            criterion = self._source.get_criterion(ref)
            covered = criterion.get("covered_domain")
            if not isinstance(covered, list) or not covered:
                diagnostics.append(_diagnostic("INCOMPLETE_COVERAGE", ref, "COVERED", "explicit non-empty COVERED domain is required"))
                continue
            for sample in covered:
                if not isinstance(sample, Mapping):
                    diagnostics.append(_diagnostic("SCHEMA_VIOLATION", ref, "COVERED", "covered sample must be a mapping"))
                    continue
                try:
                    vector = _predicate_vector(criterion, sample)
                except Exception:
                    diagnostics.append(_diagnostic("NONDETERMINISTIC_EVALUATION", ref, "predicates", "predicate evaluation failed"))
                    continue
                if len(vector) > 1:
                    diagnostics.append(_diagnostic("PREDICATE_OVERLAP", ref, "predicates", f"covered sample matches multiple predicates: {vector}"))
                elif not vector:
                    diagnostics.append(_diagnostic("INCOMPLETE_COVERAGE", ref, "COVERED", "covered sample matches no predicate"))
        return tuple(diagnostics)

    def run_gate(self, spec_ref: SpecificationRef) -> GateResult:
        """Evaluate the frozen specification boundary; no evidence input exists here."""
        diagnostics = list(self.validate_referential_integrity(spec_ref))
        if not diagnostics:
            criterion_set_hash = self._source.get_specification(spec_ref.spec_hash)["criterion_set_ref"]
            diagnostics.extend(self.run_criterion_self_tests(criterion_set_hash))
            diagnostics.extend(self.verify_predicate_coverage(criterion_set_hash))
        unique = tuple(dict.fromkeys(diagnostics))
        status = GateStatus.FAIL if unique else GateStatus.PASS
        hashes = (spec_ref.spec_hash,)
        if not unique:
            hashes += (self._source.get_specification(spec_ref.spec_hash)["criterion_set_ref"],)
        return GateResult(status, spec_ref, hashes, unique)


__all__ = (
    "ArtifactSource", "Diagnostic", "GateResult", "GateStatus", "MappingArtifactSource",
    "SpecificationGate", "SpecificationRef",
)
