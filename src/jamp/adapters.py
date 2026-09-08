"""Simple interfaces for pluggable generators and knowledge sources."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .core import Candidate, Evidence


class Generator(Protocol):
    def generate(self, prompt: str) -> Sequence[Candidate]: ...


class KnowledgeSource(Protocol):
    def search(self, statement: str) -> Sequence[Evidence]: ...


@dataclass
class StaticGenerator:
    candidates: Sequence[Candidate]

    def generate(self, prompt: str) -> Sequence[Candidate]:
        return self.candidates


@dataclass
class StaticKnowledge:
    evidence: Sequence[Evidence]

    def search(self, statement: str) -> Sequence[Evidence]:
        return self.evidence
