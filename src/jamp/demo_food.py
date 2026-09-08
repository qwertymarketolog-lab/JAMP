"""Synthetic Food Lab demo; no medical or real-world safety claims."""
from .adapters import StaticGenerator, StaticKnowledge
from .core import Candidate, Evidence
from .engine import JAMPEngine


def build_demo() -> JAMPEngine:
    generator = StaticGenerator(
        [
            Candidate("food-001", "Buckwheat with mushrooms and parmesan"),
            Candidate("food-002", "Apple, tomato and chocolate soup"),
            Candidate("food-003", "Pasta with mushrooms and parmesan"),
        ]
    )
    knowledge = StaticKnowledge(
        [
            Evidence("recipe-db-1", "Buckwheat with mushrooms and parmesan is a known recipe pattern."),
        ]
    )
    return JAMPEngine(generator, knowledge)


if __name__ == "__main__":
    engine = build_demo()
    for result in engine.run("Generate a new fusion dish"):
        print(result.candidate.candidate_id, result.status.value, "|", result.reason)
