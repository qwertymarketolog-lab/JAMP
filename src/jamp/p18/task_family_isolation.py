"""P18.2 task-family isolation boundary.

The boundary is deliberately non-heuristic: it validates ownership and
integrity of evidence crossing the task-family boundary and rejects foreign
or unbound evidence by default.  It does not make search, policy, or replay
decisions.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .experiment_registry import ExperimentArtifact, ExperimentRegistry


class TaskFamilyBoundary:
    """Fail-closed ownership boundary for one task family.

    P18.2 intentionally implements zero-transfer semantics.  Evidence must
    carry an explicit family identity, and that identity must match the
    boundary.  Artifacts additionally have to pass their own cryptographic
    digest verification before they can cross the boundary.
    """

    def __init__(self, task_family: str) -> None:
        if not isinstance(task_family, str) or not task_family:
            raise ValueError("task family must be a non-empty string")
        self._task_family = task_family

    @property
    def task_family(self) -> str:
        return self._task_family

    @staticmethod
    def _family_of(value: Mapping[str, Any]) -> str:
        """Return an explicit family identity; reject unbound evidence."""
        task_family = value.get("task_family")
        family_id = value.get("family_id")

        if task_family is not None and family_id is not None and task_family != family_id:
            raise ValueError("task family identity mismatch")

        family = task_family if task_family is not None else family_id
        if not isinstance(family, str) or not family:
            raise ValueError("evidence has no task family identity")
        return family

    def _validate_mapping(self, value: Any, *, channel: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise TypeError(f"{channel} evidence must be a mapping")
        family = self._family_of(value)
        if family != self._task_family:
            raise ValueError(
                f"task-family isolation violation: {family!r} cannot cross into {self._task_family!r}"
            )
        return value

    def accept_policy_update(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and detach a policy-update event owned by this family."""
        self._validate_mapping(event, channel="policy update")
        return deepcopy(dict(event))

    def accept_pattern(self, pattern: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and detach a pattern record owned by this family."""
        self._validate_mapping(pattern, channel="pattern")
        return deepcopy(dict(pattern))

    def lookup_artifact(self, registry: ExperimentRegistry, experiment_id: str) -> ExperimentArtifact:
        """Look up an artifact and expose it only when it belongs to this family."""
        if not isinstance(registry, ExperimentRegistry):
            raise TypeError("registry must be an ExperimentRegistry")
        artifact = registry.get(experiment_id)
        self._validate_artifact(artifact)
        return artifact

    def _validate_artifact(self, artifact: ExperimentArtifact) -> ExperimentArtifact:
        if not isinstance(artifact, ExperimentArtifact):
            raise TypeError("boundary accepts only ExperimentArtifact")
        if not artifact.verify():
            raise ValueError("experiment artifact digest verification failed")
        family = self._family_of(artifact.payload)
        if family != self._task_family:
            raise ValueError(
                f"task-family isolation violation: {family!r} cannot cross into {self._task_family!r}"
            )
        return artifact

    def accept_artifact(self, artifact: ExperimentArtifact) -> ExperimentArtifact:
        """Accept a sealed artifact only if its cryptographic identity is valid."""
        return self._validate_artifact(artifact)

    def accept_artifact_payload(self, payload: Mapping[str, Any]) -> ExperimentArtifact:
        """Reconstruct and verify an artifact before applying family ownership."""
        if not isinstance(payload, Mapping):
            raise TypeError("artifact payload must be a mapping")
        artifact = ExperimentArtifact.from_dict(payload)
        return self._validate_artifact(artifact)

    def accept_replay(self, replay: Mapping[str, Any]) -> dict[str, Any]:
        """Validate replay lineage ownership without performing replay."""
        self._validate_mapping(replay, channel="replay")
        return deepcopy(dict(replay))

    def accept_shared_reference(self, reference: Mapping[str, Any]) -> dict[str, Any]:
        """Validate ownership and detach a reference from foreign mutable state."""
        self._validate_mapping(reference, channel="shared reference")
        return deepcopy(dict(reference))

    def accept_evidence(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        """Fail-closed gate for composite evidence; no cross-family transfer."""
        self._validate_mapping(evidence, channel="evidence")
        return deepcopy(dict(evidence))
