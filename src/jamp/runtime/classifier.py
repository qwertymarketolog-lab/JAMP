from __future__ import annotations
class TaskClassifier:
    def __init__(self,entropy_threshold:float=.85)->None:self.entropy_threshold=entropy_threshold
    def classify(self,payload:dict)->str:
        if payload.get("force_compliance",False):return "strict_compliance_safety"
        if float(payload.get("classification_entropy",0))>self.entropy_threshold:return "strict_compliance_safety"
        if int(payload.get("token_count",0))>16000:return "long_context_analysis"
        if payload.get("tools") or payload.get("intent")=="tool_execution_agent":return "tool_execution_agent"
        if payload.get("intent")=="search_and_extraction":return "search_and_extraction"
        raise ValueError("Unable to classify payload fail-closed")
