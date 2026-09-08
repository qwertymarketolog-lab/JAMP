from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
class InterpretationIntegrityError(ValueError): pass
class InterpretationClassification(str, Enum):
    SUPPORTS="SUPPORTS"; REFUTES="REFUTES"; UNDETERMINED="UNDETERMINED"
_FORBIDDEN={"timestamp","uuid","pid","process_id","hostname","memory_address","environment","local_path"}
def _check_runtime(v):
    if isinstance(v,Mapping):
        for k,x in v.items():
            if str(k).lower() in _FORBIDDEN: raise InterpretationIntegrityError(f"runtime metadata forbidden: {k}")
            _check_runtime(x)
    elif isinstance(v,(tuple,list)):
        for x in v:_check_runtime(x)
def _canon(v):
    if isinstance(v,Mapping): return {str(k):_canon(v[k]) for k in sorted(v,key=lambda x:str(x))}
    if isinstance(v,(tuple,list)): return [_canon(x) for x in v]
    if isinstance(v,Enum): return v.value
    return v
def _freeze(v):
    if isinstance(v,Mapping): return MappingProxyType({str(k):_freeze(x) for k,x in sorted(v.items(),key=lambda kv:str(kv[0]))})
    if isinstance(v,(tuple,list)): return tuple(_freeze(x) for x in v)
    return v
def _hash(v): return hashlib.sha256(json.dumps(_canon(v),sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
@dataclass(frozen=True)
class InterpretationRecord:
    interpretation_hash:str; result_hash:str; analytical_target:Any; method:str; parameters:Any; conclusion:str; classification:InterpretationClassification; evidence:Any; execution_hash:str|None; question_hash:str|None; plan_hash:str|None; trace_hash:str|None; state_hash:str|None
    def canonical_payload(self): return {"result_hash":self.result_hash,"analytical_target":_canon(self.analytical_target),"method":self.method,"parameters":_canon(self.parameters),"conclusion":self.conclusion,"classification":self.classification.value,"evidence":_canon(self.evidence),"execution_hash":self.execution_hash,"question_hash":self.question_hash,"plan_hash":self.plan_hash,"trace_hash":self.trace_hash,"state_hash":self.state_hash}
    def provenance_chain(self):
        return tuple(x for x in (self.question_hash,self.plan_hash,self.execution_hash,self.result_hash,self.trace_hash,self.state_hash) if x is not None)
    def verify(self,registry=None):
        if registry is not None:
            r=registry.get(self.result_hash)
            if r is None: raise InterpretationIntegrityError("unknown result_hash")
            verifier=getattr(r,"verify",None)
            if callable(verifier) and not verifier(): raise InterpretationIntegrityError("result integrity failed")
            for a in ("execution_hash","question_hash","plan_hash","trace_hash","state_hash"):
                e=getattr(r,a,None)
                if e is not None and getattr(self,a)!=e: raise InterpretationIntegrityError(f"provenance mismatch: {a}")
        if _hash(self.canonical_payload())!=self.interpretation_hash: raise InterpretationIntegrityError("interpretation hash mismatch")
        if not self.method or not self.conclusion: raise InterpretationIntegrityError("method and conclusion are required")
        if not isinstance(self.classification,InterpretationClassification): raise InterpretationIntegrityError("invalid classification")
        _check_runtime(self.canonical_payload()); return True
    def export(self): self.verify(); return {"interpretation_hash":self.interpretation_hash,**self.canonical_payload()}
def make_interpretation(*,result_hash,analytical_target,method,parameters,conclusion,classification,evidence=None,registry=None):
    if registry is None or result_hash not in registry: raise InterpretationIntegrityError("registered result is required")
    _check_runtime(parameters); _check_runtime(analytical_target); _check_runtime(evidence)
    r=registry[result_hash]; verifier=getattr(r,"verify",None)
    if callable(verifier) and not verifier(): raise InterpretationIntegrityError("result integrity failed")
    try: classification=InterpretationClassification(classification)
    except ValueError as e: raise InterpretationIntegrityError("invalid classification") from e
    rec=InterpretationRecord("",result_hash,_freeze(analytical_target),str(method),_freeze(parameters),str(conclusion),classification,_freeze(evidence),getattr(r,"execution_hash",None),getattr(r,"question_hash",None),getattr(r,"plan_hash",None),getattr(r,"trace_hash",None),getattr(r,"state_hash",None))
    object.__setattr__(rec,"interpretation_hash",_hash(rec.canonical_payload())); rec.verify(registry); return rec
