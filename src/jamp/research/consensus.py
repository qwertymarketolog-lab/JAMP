"""P20.10 deterministic claim synthesis and consensus resolution.

Research-only, content-addressed, immutable, and epistemically bounded.
Interpretations are evidence-bearing inputs; consensus is a structured
resolution state, never an assertion of absolute truth.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib, re
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from .canonical import canonical_bytes

_HASH=re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN=frozenset({"timestamp","uuid","pid","process_id","hostname","memory_address","environment","local_path"})
class ConsensusIntegrityError(ValueError): pass
class ConsensusStatus(str,Enum):
    CONSENSUS="CONSENSUS"; CONTESTED="CONTESTED"; UNDETERMINED="UNDETERMINED"
class EpistemicStatus(str,Enum): FALSIFIABLE="FALSIFIABLE"

def _check(v:Any)->None:
    if isinstance(v,Mapping):
        for k,x in v.items():
            if str(k).lower() in _FORBIDDEN: raise ConsensusIntegrityError(f"runtime metadata forbidden: {k}")
            if not isinstance(k,str): raise ConsensusIntegrityError("mapping keys must be strings")
            _check(x)
    elif isinstance(v,(list,tuple)):
        for x in v:_check(x)
def _plain(v:Any)->Any:
    if isinstance(v,Enum): return v.value
    if isinstance(v,Mapping): return {str(k):_plain(x) for k,x in sorted(v.items(),key=lambda x:str(x[0]))}
    if isinstance(v,(list,tuple)): return [_plain(x) for x in v]
    return v
def _freeze(v:Any)->Any:
    _check(v)
    if isinstance(v,Mapping): return MappingProxyType({k:_freeze(x) for k,x in sorted(v.items())})
    if isinstance(v,(list,tuple)): return tuple(_freeze(x) for x in v)
    return v
def _sha(v:Any)->str: return hashlib.sha256(canonical_bytes(_plain(v))).hexdigest()
def _hash_id(v:str,f:str)->None:
    if not isinstance(v,str) or not _HASH.fullmatch(v): raise ConsensusIntegrityError(f"{f} must be lowercase SHA-256")
def _classification(i:Any)->str:
    v=getattr(getattr(i,"classification",None),"value",getattr(i,"classification",None))
    if v not in {"SUPPORTS","REFUTES","UNDETERMINED"}: raise ConsensusIntegrityError("invalid interpretation classification")
    return v
def compute_consensus_hash(payload:Mapping[str,Any])->str:return _sha(payload)
def compute_claim_hash(payload:Mapping[str,Any])->str:return _sha(payload)

@dataclass(frozen=True,slots=True)
class ConsensusRecord:
    consensus_hash:str; status:ConsensusStatus; supporting_hashes:tuple[str,...]; conflicting_hashes:tuple[str,...]; dissenting_hashes:tuple[str,...]
    def canonical_payload(self): return {"status":self.status.value,"supporting_hashes":list(self.supporting_hashes),"conflicting_hashes":list(self.conflicting_hashes),"dissenting_hashes":list(self.dissenting_hashes)}
    def verify(self):
        _hash_id(self.consensus_hash,"consensus_hash")
        if _sha(self.canonical_payload())!=self.consensus_hash: raise ConsensusIntegrityError("consensus hash mismatch")
        if self.status==ConsensusStatus.CONSENSUS and self.conflicting_hashes: raise ConsensusIntegrityError("false consensus")
        return True

@dataclass(frozen=True,slots=True)
class ClaimRecord:
    claim_hash:str; statement:str; interpretation_hashes:tuple[str,...]; target:str; method:str; parameters:Any; consensus:ConsensusRecord; provenance:Mapping[str,Any]; epistemic_status:EpistemicStatus=EpistemicStatus.FALSIFIABLE; falsifiable:bool=True
    @property
    def status(self): return self.consensus.status
    @property
    def supporting_hashes(self): return self.consensus.supporting_hashes
    @property
    def conflicting_hashes(self): return self.consensus.conflicting_hashes
    @property
    def execution_hashes(self): return tuple(self.provenance["execution_hashes"])
    @property
    def plan_hashes(self): return tuple(self.provenance["plan_hashes"])
    @property
    def question_hashes(self): return tuple(self.provenance["question_hashes"])
    @property
    def trace_hashes(self): return tuple(self.provenance["trace_hashes"])
    @property
    def state_hashes(self): return tuple(self.provenance["state_hashes"])
    def canonical_payload(self): return {"statement":self.statement,"interpretation_hashes":list(self.interpretation_hashes),"target":self.target,"method":self.method,"parameters":_plain(self.parameters),"consensus":_plain(self.consensus.canonical_payload()),"provenance":_plain(self.provenance),"epistemic_status":self.epistemic_status.value,"falsifiable":self.falsifiable}
    def provenance_chain(self):
        if len(self.interpretation_hashes)==1:
            i=self.provenance["interpretation_chains"][self.interpretation_hashes[0]]
            return tuple(i)
        out=[]
        for h in self.interpretation_hashes:
            for x in self.provenance["interpretation_chains"][h]:
                if x not in out: out.append(x)
        return tuple(out)
    def verify(self,registry):
        for h in self.interpretation_hashes:
            _hash_id(h,"interpretation_hash"); item=registry.get(h)
            if item is None or getattr(item,"interpretation_hash",None)!=h: raise ConsensusIntegrityError("interpretation substitution detected")
            verifier=getattr(item,"verify",None)
            if callable(verifier):
                try: ok=verifier(registry)
                except TypeError: ok=verifier()
                if ok is not True: raise ConsensusIntegrityError("interpretation integrity failed")
        self.consensus.verify()
        if _sha(self.canonical_payload())!=self.claim_hash: raise ConsensusIntegrityError("claim hash mismatch")
        _check(self.canonical_payload()); return True
    def export(self): return {"claim_hash":self.claim_hash,**_plain(self.canonical_payload())}

def _resolve(items):
    support=tuple(sorted(getattr(i,"interpretation_hash") for i in items if _classification(i)=="SUPPORTS"))
    conflict=tuple(sorted(getattr(i,"interpretation_hash") for i in items if _classification(i)=="REFUTES"))
    unknown=tuple(sorted(getattr(i,"interpretation_hash") for i in items if _classification(i)=="UNDETERMINED"))
    status=ConsensusStatus.UNDETERMINED if not support and not conflict else ConsensusStatus.CONTESTED if support and conflict else ConsensusStatus.CONSENSUS if support and not unknown else ConsensusStatus.UNDETERMINED
    dissent=tuple(sorted(conflict+unknown)); payload={"status":status.value,"supporting_hashes":list(support),"conflicting_hashes":list(conflict),"dissenting_hashes":list(dissent)}
    return ConsensusRecord(_sha(payload),status,support,conflict,dissent)

def make_claim(registry:Mapping[str,Any],*,statement:str,interpretations:Sequence[Any],method:str,parameters:Mapping[str,Any],target:str|None=None,consensus_status:str|None=None)->ClaimRecord:
    if not isinstance(statement,str) or not statement.strip() or not isinstance(method,str) or not method.strip(): raise ConsensusIntegrityError("statement and method are required")
    if not interpretations: raise ConsensusIntegrityError("at least one verified interpretation is required")
    _check(parameters); ordered=tuple(sorted(interpretations,key=lambda x:getattr(x,"interpretation_hash","")))
    for item in ordered:
        h=getattr(item,"interpretation_hash",None); _hash_id(h,"interpretation_hash")
        if registry.get(h) is not item: raise ConsensusIntegrityError("interpretation must be registry-backed")
        verifier=getattr(item,"verify",None)
        if callable(verifier):
            try: ok=verifier(registry)
            except TypeError: ok=verifier()
            if ok is not True: raise ConsensusIntegrityError("interpretation integrity failed")
    consensus=_resolve(ordered)
    if consensus_status is not None and consensus_status!=consensus.status.value: raise ConsensusIntegrityError("manufactured consensus status")
    target=target or str(getattr(ordered[0],"analytical_target",""))
    if not target.strip(): raise ConsensusIntegrityError("target is required")
    chains={}
    for i in ordered:
        chain=tuple(i.provenance_chain()) if hasattr(i,"provenance_chain") else tuple(x for x in (getattr(i,"question_hash",None),getattr(i,"plan_hash",None),getattr(i,"execution_hash",None),getattr(i,"result_hash",None),getattr(i,"trace_hash",None),getattr(i,"state_hash",None)) if x is not None)
        chains[i.interpretation_hash]=chain
    provenance={"interpretation_hashes":[i.interpretation_hash for i in ordered],"result_hashes":sorted(getattr(i,"result_hash") for i in ordered),"execution_hashes":sorted(getattr(i,"execution_hash") for i in ordered),"plan_hashes":sorted(getattr(i,"plan_hash") for i in ordered),"question_hashes":sorted(getattr(i,"question_hash") for i in ordered),"trace_hashes":sorted(getattr(i,"trace_hash") for i in ordered),"state_hashes":sorted(getattr(i,"state_hash") for i in ordered),"interpretation_chains":chains}
    payload={"statement":" ".join(statement.split()),"interpretation_hashes":[i.interpretation_hash for i in ordered],"target":target,"method":method.strip(),"parameters":_plain(parameters),"consensus":_plain(consensus.canonical_payload()),"provenance":provenance,"epistemic_status":EpistemicStatus.FALSIFIABLE.value,"falsifiable":True}
    rec=ClaimRecord(_sha(payload),payload["statement"],tuple(payload["interpretation_hashes"]),target,method.strip(),_freeze(parameters),consensus,_freeze(provenance))
    rec.verify(registry); return rec
