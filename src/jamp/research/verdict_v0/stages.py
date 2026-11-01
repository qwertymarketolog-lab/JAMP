"""M1a scalar evidence selector and numeric-threshold criterion evaluator."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from jamp.research.verdict_v0.schema import CriterionResult, EvaluationTrace


class EvidenceSelector(Protocol):
    def select(self, evidence: dict[str, Any], selector: str) -> Any: ...


class ScalarSelector:
    def select(self, evidence: dict[str, Any], selector: str) -> Any:
        if "class" not in evidence:
            raise LookupError("evidence_class_absent")
        if evidence.get("class") != "scalar":
            raise ValueError("unsupported evidence class")
        if selector != "value" or "value" not in evidence:
            raise KeyError(selector)
        return evidence["value"]


class CriterionEvaluator(Protocol):
    def evaluate(
        self, criterion: dict[str, Any], observed: Any
    ) -> tuple[bool | Literal["unknown"], str | None]: ...


class NumericThresholdEvaluator:
    def evaluate(
        self, criterion: dict[str, Any], observed: Any
    ) -> tuple[bool | Literal["unknown"], str | None]:
        predicate = criterion.get("predicate")
        if not isinstance(predicate, dict):
            return "unknown", "observed_inconclusive"
        op, threshold = predicate.get("op"), predicate.get("threshold")
        if op not in {">=", "<="}:
            return "unknown", "observed_inconclusive"
        if (
            not isinstance(observed, (int, float))
            or isinstance(observed, bool)
            or not isinstance(threshold, (int, float))
            or isinstance(threshold, bool)
        ):
            return "unknown", "observed_inconclusive"
        return (observed >= threshold if op == ">=" else observed <= threshold), None


def evaluate_criterion(
    criterion: dict[str, Any],
    evidence: dict[str, Any],
    selector: EvidenceSelector,
    evaluator: CriterionEvaluator,
    *,
    selector_sha256: str,
    evaluator_sha256: str,
) -> CriterionResult:
    ref, selector_id = criterion["criterion_ref"], criterion.get("selector", "value")
    try:
        observed = selector.select(evidence, selector_id)
    except KeyError:
        result, reason, observed = "unknown", "selector_unresolvable", None
    except LookupError:
        result, reason, observed = "unknown", "evidence_class_absent", None
    except ValueError:
        result, reason, observed = "unknown", "selector_unresolvable", None
    else:
        result, reason = evaluator.evaluate(criterion, observed)
    if result == "unknown":
        return CriterionResult(
            ref,
            "UNKNOWN",
            EvaluationTrace(
                evaluator_sha256,
                selector_sha256,
                {
                    "class": evidence.get("class", "unknown"),
                    "selector": selector_id,
                    "observed": observed,
                },
                "unknown",
            ),
            reason or "observed_inconclusive",
        )
    return CriterionResult(
        ref,
        "PASS" if result else "FAIL",
        EvaluationTrace(
            evaluator_sha256,
            selector_sha256,
            {"class": evidence.get("class"), "selector": selector_id, "observed": observed},
            result,
        ),
        None,
    )
