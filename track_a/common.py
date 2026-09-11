"""Track A: isolated causal harness.

Self-contained symbolic engine. No JAMP-Delta phases, MCTS, learned policy,
or root-specific shortcuts. Baseline and treatment differ only in substitution
routing; all other rules and boundaries are shared.
"""
from __future__ import annotations
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class E:
    k: str; v: object = None; a: tuple["E", ...] = ()
    def __str__(self):
        if self.k in ("num", "var"): return str(self.v)
        if self.v == "=": return f"({self.a[0]}={self.a[1]})"
        if self.v == "|": return f"({self.a[0]}|{self.a[1]})"
        if self.v == "^": return f"({self.a[0]}^{self.a[1]})"
        if self.v == "*": return f"({self.a[0]}*{self.a[1]})"
        if self.v == "gcd": return f"gcd({self.a[0]},{self.a[1]},{self.a[2]})"
        if self.v in ("prime", "integer"): return f"{self.v}?({self.a[0]})"
        if self.v == ">": return f"({self.a[0]}>{self.a[1]})"
        return f"{self.v}({','.join(map(str,self.a))})"

def N(x): return E("num", int(x))
def V(x): return E("var", x)
def O(op,*args): return E("op",op,tuple(args))
def eq(a,b): return O("=",a,b)
def div(d,x): return O("|",d,x)
def mul(a,b): return O("*",a,b)
def sq(a): return O("^",a,N(2))

def walk(x):
    yield x
    for a in x.a: yield from walk(a)

def contains(x,name): return any(n.k=="var" and n.v==name for n in walk(x))

def replace(x,name,repl):
    if x.k=="var" and x.v==name: return repl
    if not x.a: return x
    return E(x.k,x.v,tuple(replace(a,name,repl) for a in x.a))

def canon(x):
    if not x.a: return x
    a=tuple(canon(y) for y in x.a)
    if x.v=="*":
        if a[0].k=="num" and a[1].k=="num": return N(a[0].v*a[1].v)
        if a[0]==N(1): return a[1]
        if a[1]==N(1): return a[0]
    if x.v=="^" and a[1]==N(1): return a[0]
    # Generic identity: (d*k)^2 = d*q^2  ->  d*k^2 = q^2.
    if x.v=="=" and len(a)==2:
        l,r=a
        if l.v=="^" and r.v=="*" and l.a[1]==N(2):
            base=l.a[0]; d,z=r.a
            if d.k=="num" and z.v=="^" and z.a[1]==N(2) and base.v=="*" and base.a[0]==d:
                return eq(mul(d,sq(base.a[1])),sq(z.a[0]))
    return E(x.k,x.v,a)

@dataclass(frozen=True)
class T:
    new:E; op:str; parents:tuple[int,...]

class State:
    def __init__(self,root,max_objects=120):
        self.root=root; self.max_objects=max_objects; self.objects=[]; self.index=set(); self.history=[]; self.max_depth=0; self.solved=False
        self.add(eq(sq(V("p")),mul(N(root),sq(V("q")))),"anchor",())
        self.add(O("prime",N(root)),"axiom",()); self.add(O("integer",V("p")),"axiom",()); self.add(O("integer",V("q")),"axiom",())
        self.add(O(">",N(root),N(1)),"axiom",()); self.add(O("gcd",V("p"),V("q"),N(1)),"axiom",())
    def add(self,e,op,parents):
        e=canon(e)
        if e in self.index or len(self.objects)>=self.max_objects:return False
        i=len(self.objects); self.objects.append(e); self.index.add(e)
        self.history.append({"step":i,"op":op,"parents":list(parents),"expr":str(e)})
        self.max_depth=max(self.max_depth,sum(1 for _ in walk(e)))
        if e.v=="contradiction":self.solved=True
        return True
    def find(self,e):
        try:return self.objects.index(canon(e))
        except ValueError:return None
    def closure(self):
        changed=True
        while changed and not self.solved:
            changed=False
            # a^2=d*b^2 -> d|a^2; prime(d) & d|x^2 -> d|x.
            for i,e in list(enumerate(self.objects)):
                if e.v=="=" and e.a[0].v=="^" and e.a[1].v=="*":
                    sqe=e.a[0]; d,z=e.a[1].a
                    if sqe.a[1]==N(2) and d.k=="num" and z.v=="^" and z.a[1]==N(2):
                        changed |= self.add(div(d,sqe.a[0]),"derive_divisibility",(i,))
                if e.v=="|" and e.a[0].k=="num" and e.a[1].v=="^" and e.a[1].a[1]==N(2):
                    d,x=e.a; pi=self.find(O("prime",d)); ii=self.find(O("integer",x.a[0]))
                    if pi is not None and ii is not None: changed |= self.add(div(d,x.a[0]),"prime_square_lemma",(i,pi,ii))
            # d|x -> x=d*k, plus integer witness; universal in d and x.
            for i,e in list(enumerate(self.objects)):
                if e.v=="|" and e.a[0].k=="num" and e.a[1].k=="var":
                    d,x=e.a; k=V(f"k_{i}")
                    changed |= self.add(eq(x,mul(d,k)),"divisibility_witness",(i,))
                    changed |= self.add(O("integer",k),"integer_witness",(i,))
            # d|p and d|q with gcd(p,q)=1 and d>1 => contradiction.
            dp=self.find(div(N(self.root),V("p"))); dq=self.find(div(N(self.root),V("q"))); g=self.find(O("gcd",V("p"),V("q"),N(1)))
            if dp is not None and dq is not None and g is not None:
                changed |= self.add(O("contradiction"),"gcd_contradiction",(dp,dq,g))

def sources(s):
    return [(i,e.a[0].v,e.a[1]) for i,e in enumerate(s.objects) if e.v=="=" and e.a[0].k=="var"]

def random_substitution(s,rng):
    ss=sources(s); rng.shuffle(ss)
    for si,name,repl in ss:
        targets=[(i,e) for i,e in enumerate(s.objects) if i!=si and contains(e,name)]
        if targets:
            ti,t=rng.choice(targets); return [T(canon(replace(t,name,repl)),"random_substitution",(si,ti))]
    return []

def target_substitution(s,rng):
    out=[]
    for si,name,repl in sources(s):
        for ti,t in enumerate(s.objects):
            if ti!=si and contains(t,name):
                n=canon(replace(t,name,repl))
                if n!=t and n not in s.index:out.append(T(n,"target_directed_substitution",(si,ti)))
    rng.shuffle(out); return out[:1]

def run(seed,root,strategy,N=200,max_objects=120):
    rng=random.Random(seed); s=State(root,max_objects); s.closure()
    for _ in range(N):
        if s.solved:break
        sub=target_substitution(s,rng) if strategy=="TREATMENT_TARGETED" else random_substitution(s,rng)
        if not sub:
            s.closure(); continue
        s.add(sub[0].new,sub[0].op,sub[0].parents); s.closure()
    stop="SOLVED" if s.solved else ("MAX_OBJECTS" if len(s.objects)>=max_objects else "MAX_ITERATIONS")
    return {"root":f"sqrt({root})","seed":seed,"strategy":strategy,"solved":s.solved,"steps":len(s.history),"progress":sum(h["op"] not in ("axiom","anchor") for h in s.history),"max_objects":len(s.objects),"ast_depth":s.max_depth,"stop_reason":stop,"trace":s.history}
