"""P20.6 deterministic research-question engine.

Research-only layer over registered evidence, verified claims, and hypothesis
references. It maps unresolved questions, gaps, and conflicts without making
unstated scientific conclusions. No production-domain, filesystem, network, or
runtime metadata dependencies are permitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_bytes

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEYS = frozenset({"timestamp", "uuid", "memory_address", "environment", "local_path", "hostname", "pid", "process_id"})
_QUESTION_TYPES = frozenset({"EXPLANATORY", "CAUSAL", "COMPARATIVE", "PREDICTIVE", "OPEN"})


class QuestionError(ValueError):
    pass


class QuestionIntegrityError(QuestionError):
    pass


class QuestionStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    CONFLICTING = "CONFLICTING"
    GAP = "GAP"
    ANSWERED = "ANSWERED"
    BLOCKED = "BLOCKED"


class QuestionType(str, Enum):
    EXPLANATORY = "EXPLANATORY"
    CAUSAL = "CAUSAL"
    COMPARATIVE = "COMPARATIVE"
    PREDICTIVE = "PREDICTIVE"
    OPEN = "OPEN"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(k in _RUNTIME_KEYS for k in value):
            raise QuestionIntegrityError("runtime metadata is forbidden")
        if any(not isinstance(k, str) for k in value):
            raise QuestionIntegrityError("mapping keys must be strings")
        return MappingProxyType({k: _freeze(value[k]) for k in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze(x) for x in value)
    if isinstance(value, tuple):
        return tuple(_freeze(x) for x in value)
    if isinstance(value, set) or isinstance(value, frozenset):
        return tuple(sorted((_freeze(x) for x in value), key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _hash(value: str, field: str) -> None:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise QuestionIntegrityError(f"{field} must be lowercase SHA-256")


def _canonical_formulation(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QuestionIntegrityError("formulation must be non-empty")
    return " ".join(value.split())


def compute_question_hash(
    formulation: str,
    question_type: str | QuestionType,
    context: Mapping[str, Any],
    constraints: Mapping[str, Any],
    evidence_hashes: Sequence[str] = (),
    claim_hashes: Sequence[str] = (),
    hypothesis_hashes: Sequence[str] = (),
    parent_question_hash: str | None = None,
) -> str:
    """Compute question identity from canonical research semantics only."""
    formulation = _canonical_formulation(formulation)
    qtype = question_type.value if isinstance(question_type, QuestionType) else question_type
    if qtype not in _QUESTION_TYPES:
        raise QuestionIntegrityError("invalid question_type")
    if parent_question_hash is not None:
        _hash(parent_question_hash, "parent_question_hash")
    refs = tuple(dict.fromkeys(tuple(evidence_hashes) + tuple(claim_hashes) + tuple(hypothesis_hashes)))
    for ref in refs:
        _hash(ref, "provenance hash")
    material = {
        "formulation": formulation,
        "question_type": qtype,
        "context": _thaw(_freeze(context)),
        "constraints": _thaw(_freeze(constraints)),
        "evidence_hashes": list(dict.fromkeys(evidence_hashes)),
        "claim_hashes": list(dict.fromkeys(claim_hashes)),
        "hypothesis_hashes": list(dict.fromkeys(hypothesis_hashes)),
        "parent_question_hash": parent_question_hash,
    }
    return hashlib.sha256(canonical_bytes(material)).hexdigest()


def _registry_evidence(registry: Any, ref: str) -> tuple[Any, Mapping[str, Any]]:
    _hash(ref, "evidence_hash")
    try:
        if not registry.contains(ref):
            raise KeyError(ref)
        evidence = registry.get(ref)
        verify = getattr(evidence, "verify_integrity", None)
        if callable(verify) and not verify():
            raise QuestionIntegrityError("evidence integrity failure")
        index = getattr(registry, "index", {})
        entry = index.get(ref) if hasattr(index, "get") else None
        if entry is not None:
            required = ("trace_hash", "initial_state_hash", "ordered_event_ids", "resulting_state_hash")
            if not all(k in entry for k in required):
                raise QuestionIntegrityError("complete evidence provenance is required")
            provenance = {
                "result_hash": ref,
                "trace_hash": entry["trace_hash"],
                "event_ids": tuple(entry["ordered_event_ids"]),
                "state_anchors": (entry["initial_state_hash"], entry["resulting_state_hash"]),
            }
        else:
            exported = evidence.export() if hasattr(evidence, "export") else {}
            provenance = {
                "result_hash": getattr(evidence, "result_hash", ref),
                "trace_hash": getattr(evidence, "trace_hash", exported.get("trace_hash")),
                "event_ids": tuple(getattr(evidence, "event_ids", exported.get("event_ids", ()))),
                "state_anchors": tuple(getattr(evidence, "state_anchors", exported.get("state_anchors", ()))),
            }
        if provenance["result_hash"] != ref:
            raise QuestionIntegrityError("evidence identity substitution detected")
        if not provenance["trace_hash"] or len(provenance["event_ids"]) == 0 or len(provenance["state_anchors"]) != 2:
            raise QuestionIntegrityError("incomplete evidence provenance")
        _hash(provenance["trace_hash"], "trace_hash")
        for item in provenance["event_ids"] + provenance["state_anchors"]:
            _hash(item, "provenance anchor")
        return evidence, MappingProxyType(provenance)
    except QuestionIntegrityError:
        raise
    except Exception as exc:
        raise QuestionIntegrityError("evidence is not registry-backed") from exc


def _verify_claims(registry: Any, claims: Sequence[Any], claim_hashes: tuple[str, ...]) -> None:
    supplied = tuple(dict.fromkeys(getattr(c, "claim_hash", None) for c in claims))
    if supplied != claim_hashes:
        raise QuestionIntegrityError("claim substitution detected")
    for claim in claims:
        if not hasattr(claim, "verify"):
            raise QuestionIntegrityError("claim integrity verification unavailable")
        try:
            claim.verify(registry)
        except Exception as exc:
            raise QuestionIntegrityError("claim integrity verification failed") from exc
        refs = tuple(getattr(claim, "evidence_refs", ()))
        for ref in refs:
            if ref not in registry.snapshot():
                raise QuestionIntegrityError("claim references unregistered evidence")


def _resolution(evidence: Sequence[Any], constraints: Mapping[str, Any], claims: Sequence[Any]) -> tuple[QuestionStatus, Mapping[str, Any]]:
    statuses: list[str] = []
    for item in evidence:
        value = getattr(item, "status", None)
        if value is None and hasattr(item, "export"):
            value = item.export().get("status")
        if isinstance(value, Enum):
            value = value.value
        if value in {"SUPPORTED", "REFUTED", "CONTRADICTED", "UNDETERMINED"}:
            statuses.append(value)
    claim_statuses = []
    for claim in claims:
        value = getattr(claim, "status", None)
        if isinstance(value, Enum):
            value = value.value
        if value in {"SUPPORTED", "REFUTED", "CONTRADICTED", "UNDETERMINED"}:
            claim_statuses.append(value)
    all_statuses = statuses + claim_statuses
    if any(s in {"CONTRADICTED"} for s in all_statuses) or ("SUPPORTED" in all_statuses and "REFUTED" in all_statuses):
        refs = tuple(getattr(x, "result_hash", None) for x in evidence if getattr(x, "result_hash", None))
        return QuestionStatus.CONFLICTING, MappingProxyType({"class": "CONFLICTING", "conflicts": tuple(refs), "explanation_refs": refs})
    required = constraints.get("required_evidence", ()) if isinstance(constraints, Mapping) else ()
    missing = tuple(ref for ref in required if ref not in {getattr(x, "result_hash", None) for x in evidence})
    if missing:
        return QuestionStatus.GAP, MappingProxyType({"class": "GAP", "missing_refs": missing, "explanation_refs": tuple(missing)})
    if all_statuses and all(s == "SUPPORTED" for s in all_statuses):
        refs = tuple(getattr(x, "result_hash", None) for x in evidence if getattr(x, "result_hash", None))
        return QuestionStatus.ANSWERED, MappingProxyType({"class": "ANSWERED", "explanation_refs": refs})
    if not all_statuses:
        return QuestionStatus.UNRESOLVED, MappingProxyType({"class": "UNRESOLVED", "explanation_refs": ()})
    return QuestionStatus.UNRESOLVED, MappingProxyType({"class": "UNRESOLVED", "explanation_refs": tuple(getattr(x, "result_hash", None) for x in evidence)})


@dataclass(frozen=True, slots=True)
class ResearchQuestion:
    formulation: str
    question_type: QuestionType
    context: Mapping[str, Any]
    constraints: Mapping[str, Any]
    evidence_hashes: tuple[str, ...]
    claim_hashes: tuple[str, ...]
    hypothesis_hashes: tuple[str, ...]
    parent_question_hash: str | None
    status: QuestionStatus
    resolution: Mapping[str, Any]
    provenance: Mapping[str, Any]
    question_hash: str

    def __post_init__(self) -> None:
        formulation = _canonical_formulation(self.formulation)
        qtype = self.question_type if isinstance(self.question_type, QuestionType) else QuestionType(self.question_type)
        context = _freeze(self.context)
        constraints = _freeze(self.constraints)
        evidence = tuple(dict.fromkeys(self.evidence_hashes))
        claims = tuple(dict.fromkeys(self.claim_hashes))
        hypotheses = tuple(dict.fromkeys(self.hypothesis_hashes))
        for ref in evidence + claims + hypotheses:
            _hash(ref, "provenance hash")
        if self.parent_question_hash is not None:
            _hash(self.parent_question_hash, "parent_question_hash")
        status = self.status if isinstance(self.status, QuestionStatus) else QuestionStatus(self.status)
        resolution = _freeze(self.resolution)
        provenance = _freeze(self.provenance)
        expected = compute_question_hash(formulation, qtype, context, constraints, evidence, claims, hypotheses, self.parent_question_hash)
        if expected != self.question_hash:
            raise QuestionIntegrityError("question_hash does not match content")
        object.__setattr__(self, "formulation", formulation)
        object.__setattr__(self, "question_type", qtype)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(self, "evidence_hashes", evidence)
        object.__setattr__(self, "claim_hashes", claims)
        object.__setattr__(self, "hypothesis_hashes", hypotheses)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "resolution", resolution)
        object.__setattr__(self, "provenance", provenance)

    @property
    def question_id(self) -> str:
        return self.question_hash

    @property
    def lineage(self) -> tuple[str, ...]:
        return (self.parent_question_hash, self.question_hash) if self.parent_question_hash else (self.question_hash,)

    def verify(self, *, registry: Any | None = None, evidence: Sequence[str] | None = None, claims: Sequence[Any] | None = None, hypotheses: Sequence[Any] | None = None) -> bool:
        if evidence is not None and tuple(evidence) != self.evidence_hashes:
            raise QuestionIntegrityError("evidence substitution detected")
        if registry is not None:
            for ref in self.evidence_hashes:
                _registry_evidence(registry, ref)
            if claims is not None:
                _verify_claims(registry, claims, self.claim_hashes)
        elif self.evidence_hashes:
            raise QuestionIntegrityError("registry is required for evidence verification")
        if hypotheses is not None:
            supplied = tuple(dict.fromkeys(getattr(h, "hypothesis_hash", None) for h in hypotheses))
            if supplied != self.hypothesis_hashes:
                raise QuestionIntegrityError("hypothesis linkage substitution detected")
            for h in hypotheses:
                if not hasattr(h, "verify") or not h.verify(registry):
                    raise QuestionIntegrityError("hypothesis integrity verification failed")
        if self.parent_question_hash and self.parent_question_hash == self.question_hash:
            raise QuestionIntegrityError("question lineage cycle")
        expected = compute_question_hash(self.formulation, self.question_type, self.context, self.constraints, self.evidence_hashes, self.claim_hashes, self.hypothesis_hashes, self.parent_question_hash)
        if expected != self.question_hash:
            raise QuestionIntegrityError("question integrity failure")
        return True

    def export(self) -> Mapping[str, Any]:
        return MappingProxyType({
            "formulation": self.formulation,
            "question_type": self.question_type.value,
            "context": _thaw(self.context),
            "constraints": _thaw(self.constraints),
            "evidence_hashes": self.evidence_hashes,
            "claim_hashes": self.claim_hashes,
            "hypothesis_hashes": self.hypothesis_hashes,
            "parent_question_hash": self.parent_question_hash,
            "status": self.status.value,
            "resolution": _thaw(self.resolution),
            "provenance": _thaw(self.provenance),
            "question_hash": self.question_hash,
        })

    @classmethod
    def from_export(cls, payload: Mapping[str, Any]) -> "ResearchQuestion":
        if not isinstance(payload, Mapping):
            raise QuestionIntegrityError("invalid question export")
        required = {"formulation", "question_type", "context", "constraints", "evidence_hashes", "claim_hashes", "hypothesis_hashes", "parent_question_hash", "status", "resolution", "provenance", "question_hash"}
        if set(payload) != required:
            raise QuestionIntegrityError("invalid question export schema")
        return cls(**payload)


def make_question(
    registry: Any,
    *,
    formulation: str,
    question_type: str | QuestionType,
    context: Mapping[str, Any],
    constraints: Mapping[str, Any],
    evidence_hashes: Sequence[str] = (),
    claim_hashes: Sequence[str] = (),
    hypothesis_hashes: Sequence[str] = (),
    parent_question_hash: str | None = None,
    status: QuestionStatus | str | None = None,
    claims: Sequence[Any] = (),
    hypotheses: Sequence[Any] = (),
) -> ResearchQuestion:
    qtype = question_type.value if isinstance(question_type, QuestionType) else question_type
    if qtype not in _QUESTION_TYPES:
        raise QuestionIntegrityError("invalid question_type")
    evidence_refs = tuple(dict.fromkeys(evidence_hashes))
    evidence: list[Any] = []
    provenance: dict[str, Any] = {}
    for ref in evidence_refs:
        item, prov = _registry_evidence(registry, ref)
        evidence.append(item)
        provenance[ref] = prov
    claim_refs = tuple(dict.fromkeys(claim_hashes))
    if claims:
        _verify_claims(registry, claims, claim_refs)
    hypothesis_refs = tuple(dict.fromkeys(hypothesis_hashes))
    if hypotheses:
        supplied = tuple(dict.fromkeys(getattr(h, "hypothesis_hash", None) for h in hypotheses))
        if supplied != hypothesis_refs:
            raise QuestionIntegrityError("hypothesis linkage substitution detected")
        for h in hypotheses:
            if not hasattr(h, "verify") or not h.verify(registry):
                raise QuestionIntegrityError("hypothesis integrity verification failed")
    if parent_question_hash is not None:
        _hash(parent_question_hash, "parent_question_hash")
        if parent_question_hash in tuple(constraints.get("lineage", ())) if isinstance(constraints, Mapping) else False:
            raise QuestionIntegrityError("cyclic research lineage")
    qhash = compute_question_hash(formulation, qtype, context, constraints, evidence_refs, claim_refs, hypothesis_refs, parent_question_hash)
    computed_status, resolution = _resolution(evidence, constraints, claims)
    if status is not None:
        requested = status if isinstance(status, QuestionStatus) else QuestionStatus(status)
        if requested in {QuestionStatus.CONFLICTING, QuestionStatus.GAP, QuestionStatus.ANSWERED} and requested != computed_status:
            raise QuestionIntegrityError("status contradicts deterministic resolution")
        if requested is QuestionStatus.BLOCKED and not (evidence_refs or claim_refs):
            computed_status = requested
            resolution = MappingProxyType({"class": "BLOCKED", "explanation_refs": ()})
        elif requested is QuestionStatus.UNRESOLVED and computed_status is QuestionStatus.GAP:
            computed_status = requested
            resolution = MappingProxyType({"class": "UNRESOLVED", "explanation_refs": ()})
    return ResearchQuestion(_canonical_formulation(formulation), QuestionType(qtype), context, constraints, evidence_refs, claim_refs, hypothesis_refs, parent_question_hash, computed_status, resolution, provenance, qhash)


def resolve_question(question: ResearchQuestion, *, evidence_statuses: Mapping[str, str] | None = None) -> ResearchQuestion:
    statuses = evidence_statuses or {}
    resolution = dict(question.resolution)
    if statuses:
        values = [statuses.get(ref) for ref in question.evidence_hashes if ref in statuses]
        if "SUPPORTED" in values and "REFUTED" in values:
            status = QuestionStatus.CONFLICTING
            resolution = {"class": "CONFLICTING", "conflicts": tuple(question.evidence_hashes), "explanation_refs": tuple(question.evidence_hashes)}
        elif values and all(v == "SUPPORTED" for v in values) and len(values) == len(question.evidence_hashes):
            status = QuestionStatus.ANSWERED
            resolution = {"class": "ANSWERED", "explanation_refs": tuple(question.evidence_hashes)}
        else:
            status = QuestionStatus.UNRESOLVED
            resolution = {"class": "UNRESOLVED", "explanation_refs": tuple(question.evidence_hashes)}
    else:
        status = question.status if question.status != QuestionStatus.UNRESOLVED else QuestionStatus.UNRESOLVED
    return ResearchQuestion(question.formulation, question.question_type, question.context, question.constraints, question.evidence_hashes, question.claim_hashes, question.hypothesis_hashes, question.parent_question_hash, status, resolution, question.provenance, question.question_hash)
