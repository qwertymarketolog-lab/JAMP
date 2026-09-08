from jamp.adapters import StaticGenerator, StaticKnowledge
from jamp.core import Candidate, Evidence, Status
from jamp.engine import JAMPEngine


def test_confirmed_candidate_is_committed() -> None:
    engine = JAMPEngine(
        StaticGenerator([Candidate("c1", "known fact")]),
        StaticKnowledge([Evidence("src1", "known fact")]),
    )
    result = engine.run("test")[0]
    assert result.status is Status.CONFIRMED
    assert len(engine.registry.by_kind("verified_candidate")) == 1
    assert engine.history[-1].event_type == "COMMIT"


def test_unsupported_candidate_stays_unknown() -> None:
    engine = JAMPEngine(
        StaticGenerator([Candidate("c2", "unknown claim")]),
        StaticKnowledge([]),
    )
    result = engine.run("test")[0]
    assert result.status is Status.UNKNOWN
    assert engine.registry.all() == ()
    assert all(event.event_type != "COMMIT" for event in engine.history)


def test_conflicting_evidence_is_not_committed() -> None:
    engine = JAMPEngine(
        StaticGenerator([Candidate("c3", "contested claim")]),
        StaticKnowledge(
            [
                Evidence("src-positive", "support", supports=True),
                Evidence("src-negative", "contradiction", supports=False),
            ]
        ),
    )
    result = engine.run("test")[0]
    assert result.status is Status.CONFLICT
    assert engine.registry.all() == ()
