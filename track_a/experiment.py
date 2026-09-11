"""Run the Track A paired ablation.

The same roots, seeds, N and max_objects are used for both arms. Results are
written only to the requested output path; no repository baseline is mutated.
"""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from .common import run

ROOTS=(2,3,5)
SEEDS=(0,1,2,42,99)

FIELDS=("root","seed","strategy","solved","steps","progress","max_objects","ast_depth","stop_reason")

def sweep(roots=ROOTS,seeds=SEEDS,N=200,max_objects=120):
    rows=[]
    for root in roots:
        for seed in seeds:
            for strategy in ("BASELINE_RANDOM","TREATMENT_TARGETED"):
                r=run(seed,root,strategy,N,max_objects)
                rows.append({k:r[k] for k in FIELDS})
                rows[-1]["trace"]=r["trace"]
    return rows

def main():
    p=argparse.ArgumentParser(); p.add_argument("--out",default="track_a/results"); p.add_argument("--N",type=int,default=200); p.add_argument("--max-objects",type=int,default=120)
    a=p.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    rows=sweep(N=a.N,max_objects=a.max_objects)
    (out/"results.json").write_text(json.dumps(rows,indent=2),encoding="utf-8")
    with (out/"results.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows([{k:r[k] for k in FIELDS} for r in rows])
    print(f"wrote {len(rows)} paired runs to {out}")

if __name__=="__main__": main()
