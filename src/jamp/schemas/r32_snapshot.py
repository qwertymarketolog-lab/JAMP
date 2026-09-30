from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class TransportState(str, Enum):
    STABLE = "TRANSPORT_STABLE"
    DEGRADED = "TRANSPORT_DEGRADED"
    UNSTABLE = "TRANSPORT_UNSTABLE"
    UNAVAILABLE = "UNAVAILABLE"


class EvaluationState(str, Enum):
    STABLE = "STABLE"
    TRANSPORT_DEGRADED = "TRANSPORT_DEGRADED"
    TRANSPORT_UNSTABLE = "TRANSPORT_UNSTABLE"
    PERFORMANCE_DRIFT = "PERFORMANCE_DRIFT"
    BEHAVIORAL_DRIFT = "BEHAVIORAL_DRIFT"
    SEMANTIC_ANOMALY = "SEMANTIC_ANOMALY"
    UNAVAILABLE = "UNAVAILABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


class SemanticReferenceSpec(BaseModel):
    reference_id: str = "IAU-RES-B5-B6-2006"
    reference_source: str = "International Astronomical Union"
    required_facts: List[str] = Field(
        default_factory=lambda: [
            "orbits_sun",
            "hydrostatic_equilibrium",
            "cleared_neighborhood",
        ]
    )
    forbidden_claims: List[str] = Field(
        default_factory=lambda: [
            "minor_planet",
            "regular_planet",
            "asteroid",
        ]
    )


class ModelDriftEvaluation(BaseModel):
    model_id: str
    baseline_id: str = "R32-BASELINE-T0"
    k_iterations: int = Field(default=15, ge=1)
    failures_count: int = Field(ge=0)
    p50_latency_ms_t0: float = Field(gt=0)
    p50_latency_ms_tn: float = Field(gt=0)
    p95_latency_ms_t0: float = Field(gt=0)
    p95_latency_ms_tn: float = Field(gt=0)
    format_compliance_count: int = Field(ge=0)
    semantic_compliance_count: int = Field(ge=0)
    final_state: EvaluationState

    def compute_transport_state(self) -> TransportState:
        if self.failures_count >= self.k_iterations:
            return TransportState.UNAVAILABLE

        failure_rate = self.failures_count / self.k_iterations
        if failure_rate >= 0.20:
            return TransportState.UNSTABLE
        if failure_rate > 0.0:
            return TransportState.DEGRADED
        return TransportState.STABLE

    def is_performance_drift(self) -> bool:
        p50_shift = abs(self.p50_latency_ms_tn - self.p50_latency_ms_t0) / self.p50_latency_ms_t0
        p95_shift = abs(self.p95_latency_ms_tn - self.p95_latency_ms_t0) / self.p95_latency_ms_t0
        return p50_shift > 0.25 or p95_shift > 0.25
