from .common import run

STRATEGY = "BASELINE_RANDOM"

def execute(seed, root, N=200, max_objects=120):
    return run(seed, root, STRATEGY, N=N, max_objects=max_objects)

if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("--seed",type=int,default=42); p.add_argument("--root",type=int,default=2); p.add_argument("--N",type=int,default=200)
    a=p.parse_args(); r=execute(a.seed,a.root,a.N)
    print(r)
