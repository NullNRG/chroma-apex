"""CPU logits selection microbench. NO pretrained weights are involved.

All reported data are diagnostic microbenchmarks only. Compare full pretrained
model inference with pretrained_engine.py on machines with model weights.
"""
from __future__ import annotations
import argparse, json, time, statistics
import numpy as np
import torch
from pretrained_engine import ApexSelector,TorchTopKSelector,TorchExactSelector,TorchOptimizedSelector,AdaptiveSelector


def bench(n: int, distribution: str, k: int, p: float, *, reps=140, rounds=5, seed=701):
    rng = np.random.default_rng(seed+n+k)
    if distribution == 'normal':
        logits = rng.standard_normal(n).astype('float32')
    elif distribution == 'peaky':
        logits = rng.standard_normal(n).astype('float32')*.55
        logits[rng.choice(n,10,replace=False)] += rng.uniform(6,10,10)
    elif distribution == 'ties':
        logits = rng.integers(-12,12,size=n).astype('float32')
    else:
        raise ValueError(distribution)
    x = torch.from_numpy(logits)
    selectors = dict(apex=ApexSelector(),torch_topk=TorchTopKSelector(),torch_exact=TorchExactSelector(),torch_optimized=TorchOptimizedSelector(),adaptive=AdaptiveSelector())
    # Exclude full stable sorting reference from timed results, but verify the same sample.
    expected = selectors['torch_exact'].select(x,k,p,.85,.3345)
    got = selectors['apex'].select(x,k,p,.85,.3345)
    if expected != got:
        raise AssertionError(f'sampling output mismatch n={n},k={k},p={p} expected={expected},got={got}')
    methods = ('apex','torch_topk','torch_optimized','adaptive')
    for sampler in selectors.values():
        for _ in range(10):
            sampler.select(x,k,p,.85,.3345)
    per = dict.fromkeys(methods)
    for m in methods:per[m]=[]
    for i in range(rounds):
        todo=methods[i%len(methods):]+methods[:i%len(methods)]
        for m in todo:
            sel=selectors[m]
            start=time.perf_counter_ns()
            for j in range(reps):
                sel.select(x,k,p,.85,.3345)
            per[m].append((time.perf_counter_ns()-start)/reps/1e3)
    med={m:round(statistics.median(per[m]),3) for m in methods}
    return dict(n=n,distribution=distribution,top_k=k,top_p=p,median_us_per_token=med,
                apex_vs_torch_topk_speedup=round(med['torch_topk']/med['apex'],3),
                apex_vs_optimized_speedup=round(med['torch_optimized']/med['apex'],3),
                adaptive_vs_optimized_speedup=round(med['torch_optimized']/med['adaptive'],3),
                exact_reference_token=expected,samples_per_round=reps,rounds=rounds)


def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--reps',type=int,default=140)
    pa.add_argument('--rounds',type=int,default=5)
    pa.add_argument('--output',default='selector_microbench.json')
    args=pa.parse_args()
    torch.set_num_threads(1)
    tests=[(8192,'normal',40,.95),(50257,'normal',40,.95),
           (50257,'peaky',40,.95),(50257,'normal',0,.95),
           (50257,'ties',40,.95),(128256,'normal',40,.95),
           (128256,'normal',0,.95),(50257,'normal',1,1.0)]
    results=[]
    for n,dist,k,p in tests:
        result=bench(n,dist,k,p,reps=args.reps,rounds=args.rounds)
        results.append(result)
        print(f'{n:>7} {dist:<6} k={k:<3} apex={result["median_us_per_token"]["apex"]:>9.2f}us torch_topk={result["median_us_per_token"]["torch_topk"]:>9.2f}us optimized={result["median_us_per_token"]["torch_optimized"]:>9.2f}us adaptive={result["median_us_per_token"]["adaptive"]:>9.2f}us adaptive_ratio={result["adaptive_vs_optimized_speedup"]:.2f}x',flush=True)
    from pathlib import Path
    Path(args.output).write_text(json.dumps({'environment':dict(torch_version=torch.__version__,threads=1,device='cpu',pretrained_model_weights=False), 'cases':results},indent=2)+'\n')
if __name__=='__main__':main()
