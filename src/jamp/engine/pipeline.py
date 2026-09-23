"""JAMP Pipeline integrated with the authoritative Commit Gateway."""
from __future__ import annotations

from typing import Dict, List

from jamp.engine.commit import CommitManager, CommitReceipt
from jamp.engine.evaluate import VerificationEngine
from jamp.events.dag import EventDAG
from jamp.registry.candidates import Candidate
from jamp.registry.registry import Registry


class JAMPPipeline:
    def __init__(self, knowledge_base: Dict[str, bool]):
        self.registry = Registry()
        self.dag = EventDAG()
        self.verifier = VerificationEngine(knowledge_base)
        self.commit_manager = CommitManager(self.registry, self.dag)

    def process_candidates(self, candidates: List[Candidate]) -> List[CommitReceipt]:
        receipts: List[CommitReceipt] = []
        for candidate in candidates:
            verification_result = self.verifier.verify_candidate(candidate)
            receipts.append(self.commit_manager.commit(verification_result))
        return receipts
