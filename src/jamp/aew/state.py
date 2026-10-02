from __future__ import annotations

from dataclasses import dataclass

from jamp.aew.contract import ResearchState

_ALLOWED: dict[ResearchState, frozenset[ResearchState]] = {
    ResearchState.OPEN: frozenset({ResearchState.INVESTIGATING}),
    ResearchState.INVESTIGATING: frozenset(
        {
            ResearchState.HYPOTHESIS_FORMED,
            ResearchState.INCONCLUSIVE,
            ResearchState.FAILED,
        }
    ),
    ResearchState.HYPOTHESIS_FORMED: frozenset(
        {ResearchState.EXPERIMENT_DEFINED, ResearchState.INCONCLUSIVE}
    ),
    ResearchState.EXPERIMENT_DEFINED: frozenset(
        {ResearchState.RUNNING, ResearchState.INCONCLUSIVE}
    ),
    ResearchState.RUNNING: frozenset({ResearchState.EVIDENCE_COLLECTED, ResearchState.FAILED}),
    ResearchState.EVIDENCE_COLLECTED: frozenset(
        {
            ResearchState.VERIFIED,
            ResearchState.INCONCLUSIVE,
            ResearchState.INVESTIGATING,
        }
    ),
    ResearchState.VERIFIED: frozenset({ResearchState.CLOSED}),
    ResearchState.INCONCLUSIVE: frozenset({ResearchState.INVESTIGATING, ResearchState.CLOSED}),
    ResearchState.FAILED: frozenset({ResearchState.INVESTIGATING, ResearchState.CLOSED}),
    ResearchState.CLOSED: frozenset(),
}


@dataclass
class StateMachine:
    state: ResearchState = ResearchState.OPEN

    def transition(self, target: ResearchState) -> ResearchState:
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"invalid AEW transition: {self.state.value} -> {target.value}")
        self.state = target
        return self.state

    @staticmethod
    def allowed_from(state: ResearchState) -> frozenset[ResearchState]:
        return _ALLOWED[state]
