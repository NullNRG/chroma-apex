"""CHROMA APEX LLM inference experiment.

Requires PyTorch, NumPy, and the compiled native sampler. The bundled decoder
configurations use deterministic RANDOM weights, not pretrained language models.
For pretrained checkpoints, --hf-model accepts a LOCAL Hugging Face directory
if the optional transformers dependency and checkpoint exist.
"""
import argparse
import ctypes
import json
import math
import os
from pathlib import Path
import statistics
import time

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]

class Stats(ctypes.Structure):
    _fields_=[('candidate_count',ctypes.c_uint32),('retained_count',ctypes.c_uint32),('strategy',ctypes.c_uint32)]

class ApexSampler:
    def __init__(self, lib=None, strategy=0):
        if lib is None:
            lib=ROOT/'build'/'libapex_llm.so'
        self.lib=ctypes.CDLL(str(lib))
        self.fn=self.lib.apx_llm_sample
        self.fn.argtypes=[ctypes.POINTER(ctypes.c_float),ctypes.c_uint32,
                          ctypes.c_float,ctypes.c_uint32,ctypes.c_float,
                          ctypes.c_double,ctypes.POINTER(ctypes.c_uint32),
                          ctypes.POINTER(Stats),ctypes.c_int]
        self.fn.restype=ctypes.c_int
        self.strategy=strategy
    def sample(self, logits, k=40, p=.95, temperature=.8, u=.5):
        if isinstance(logits,torch.Tensor):
            logits=logits.detach().float().contiguous().numpy()
        logits=np.ascontiguousarray(logits,dtype=np.float32)
        o=ctypes.c_uint32()
        st=Stats()
        rc=self.fn(logits.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),logits.size,
                    temperature,k,p,u,ctypes.byref(o),ctypes.byref(st),self.strategy)
        if rc:raise RuntimeError(f'native sampler status {rc}')
        return o.value

class TorchSampler:
    """CPU-native torch.topk + explicit ascending-ID tie normalization."""
    def sample(self, logits, k=40, p=.95, temperature=.8, u=.5):
        if isinstance(logits,np.ndarray):logits=torch.from_numpy(logits)
        x=logits.detach().float().flatten()
        valid=~torch.isnan(x) & (x != float('-inf'))
        if not torch.any(valid):raise ValueError('all masked')
        # This matches the native CPU reference for ordinary finite logits.
        allowed=torch.nonzero(valid,as_tuple=False).flatten()
        vals=x[allowed]
        best=torch.argmax(vals).item()
        if temperature == 0 or k==1: return int(allowed[best])
        posinf=torch.isposinf(vals)
        if posinf.any():
            allowed=allowed[posinf];vals=vals[posinf]
        if k and k < allowed.numel():
            vals,loc=torch.topk(vals,k,sorted=True)
            allowed=allowed[loc]
        else:
            vals,loc=torch.sort(vals,descending=True,stable=True)
            allowed=allowed[loc]
        # Most model logits have no exact ties. Sort by token ID on ties to
        # make the sampling distribution's ordering deterministic.
        ids=allowed.numpy(); a=vals.numpy()
        order=np.lexsort((ids,-a))
        vals=vals[torch.from_numpy(order.copy())]
        allowed=allowed[torch.from_numpy(order.copy())]
        if torch.isposinf(vals).any():
            weights=torch.ones(vals.numel(),dtype=torch.float64)
        else:
            weights=torch.exp((vals.double()-vals[0].double())/temperature)
        masses=torch.cumsum(weights,0)
        keep=int(torch.searchsorted(masses, (masses[-1]*p).clone(), right=False))+1
        target=u*float(masses[keep-1])
        j=int(torch.searchsorted(masses[:keep],torch.tensor(target,dtype=torch.float64),right=True))
        return int(allowed[min(j,keep-1)])

class TorchFastSampler:
    """Common direct torch.topk/torch.softmax pipeline (float32, no tie repair)."""
    def sample(self, logits, k=40, p=.95, temperature=.8, u=.5):
        if isinstance(logits,np.ndarray):logits=torch.from_numpy(logits)
        logits=logits.detach().float().flatten()
        x=torch.where(torch.isnan(logits),-float('inf'),logits)
        if temperature == 0 or k==1:
            return int(torch.argmax(x).item())
        if k and k<x.numel():
            values,idx=torch.topk(x,k,largest=True,sorted=True)
        else:
            values,idx=torch.sort(x,descending=True)
        valid=(values != -float('inf'))
        values=values[valid];idx=idx[valid]
        if values.numel()==0:raise ValueError('no candidates')
        if torch.isposinf(values).any():
            good=torch.isposinf(values);values=values[good];idx=idx[good]
            mass=torch.ones_like(values)
        else:
            mass=torch.softmax(values/temperature,0)
        cumulative=torch.cumsum(mass,0)
        keep=int(torch.searchsorted(cumulative,cumulative[-1]*p,right=False).item())+1
        cutoff=cumulative[keep-1]
        target=torch.tensor(u,dtype=cumulative.dtype)*cutoff
        j=int(torch.searchsorted(cumulative[:keep],target,right=True).item())
        return int(idx[min(j,keep-1)].item())

class Norm(nn.Module):
    def __init__(self, dim):super().__init__(); self.scale=nn.Parameter(torch.ones(dim))
    def forward(self,x):return x * torch.rsqrt(x.square().mean(dim=-1,keepdim=True)+1e-5)*self.scale

class Block(nn.Module):
    def __init__(self,dim,heads,kv_heads):
        super().__init__();self.heads=heads;self.kv_heads=kv_heads;self.dim=dim//heads
        self.ln1=Norm(dim);self.ln2=Norm(dim)
        self.q=nn.Linear(dim,dim,bias=False);self.k=nn.Linear(dim,kv_heads*self.dim,bias=False)
        self.v=nn.Linear(dim,kv_heads*self.dim,bias=False);self.o=nn.Linear(dim,dim,bias=False)
        self.fc=nn.Linear(dim,4*dim,bias=False);self.out=nn.Linear(4*dim,dim,bias=False)
    def forward(self,x,kv):
        z=self.ln1(x);b=x.shape[0]
        q=self.q(z).reshape(b,self.heads,1,self.dim)
        k=self.k(z).reshape(b,self.kv_heads,1,self.dim)
        v=self.v(z).reshape(b,self.kv_heads,1,self.dim)
        if kv is not None:
            k=torch.cat((kv[0],k),dim=2);v=torch.cat((kv[1],v),dim=2)
        kr=k.repeat_interleave(self.heads//self.kv_heads,dim=1)
        vr=v.repeat_interleave(self.heads//self.kv_heads,dim=1)
        attn=torch.softmax(q @ kr.transpose(-1,-2)/math.sqrt(self.dim),dim=-1)
        x=x+self.o((attn @ vr).transpose(1,2).reshape(b,1,-1))
        x=x+self.out(F.silu(self.fc(self.ln2(x))))
        return x,(k,v)

class Decoder(nn.Module):
    def __init__(self, vocab,hidden,heads,kv_heads,layers):
        super().__init__();self.config=(vocab,hidden,heads,kv_heads,layers)
        self.embed=nn.Embedding(vocab,hidden)
        self.pos_embed=nn.Embedding(2048,hidden)
        self.blocks=nn.ModuleList([Block(hidden,heads,kv_heads) for _ in range(layers)])
        self.final=Norm(hidden)
        self.projection=nn.Linear(hidden,vocab,bias=False)
        # Deterministic, untrained and independent projection. Weight tying on
        # random weights makes the decoder repeat the input token indefinitely,
        # making token-selection parity tests nearly vacuous.
        nn.init.normal_(self.embed.weight,mean=0.0,std=0.12)
        nn.init.normal_(self.pos_embed.weight,mean=0.0,std=0.12)
        nn.init.normal_(self.projection.weight,mean=0.0,std=0.05)
    def forward_token(self,token,cache):
        position=cache[0][0].shape[2] if cache and cache[0] is not None else 0
        if position>=2048: raise ValueError('demo positional cache exceeded')
        x=self.embed(token.reshape(1,1))+self.pos_embed(torch.tensor([[position]]))
        next_cache=[]
        for layer,kv in zip(self.blocks,cache):
            x,kv=layer(x,kv);next_cache.append(kv)
        return self.projection(self.final(x)).reshape(-1),next_cache

CONFIGS={
 'dense-small':dict(vocab=8192,hidden=192,heads=4,kv_heads=4,layers=3),
 'gqa-medium':dict(vocab=16384,hidden=256,heads=8,kv_heads=2,layers=4),
 'gqa-wide':dict(vocab=32768,hidden=320,heads=10,kv_heads=2,layers=5),
}

def create_model(name, checkpoint=None):
    torch.manual_seed(713)
    model=Decoder(**CONFIGS[name]).eval()
    if checkpoint:
        obj=torch.load(checkpoint,map_location='cpu',weights_only=True)
        model.load_state_dict(obj)
    return model

def run_decode(model,sampler,tokens,seed,top_k,top_p,temp,context_prompt=None):
    rng=np.random.default_rng(seed)
    v=model.config[0]
    prefix=context_prompt or [5,11,17,19]
    if any(not 0<=x<v for x in prefix):raise ValueError('prompt token outside vocab')
    cache=[None]*len(model.blocks)
    with torch.inference_mode():
        for tok in prefix[:-1]: _,cache=model.forward_token(torch.tensor(tok),cache)
        current=prefix[-1]
        emitted=[]; model_ms=0.; sampler_ms=0.; begin=time.perf_counter()
        for _ in range(tokens):
            a=time.perf_counter()
            logits,cache=model.forward_token(torch.tensor(current),cache)
            b=time.perf_counter()
            current=sampler.sample(logits,top_k,top_p,temp,float(rng.random()))
            c=time.perf_counter()
            emitted.append(current);model_ms+=(b-a)*1000;sampler_ms+=(c-b)*1000
        elapsed=(time.perf_counter()-begin)*1000
    return dict(tokens=tokens,total_ms=elapsed,model_ms=model_ms,sampler_ms=sampler_ms,
                tokens_per_second=tokens/(elapsed/1000),token_ids=emitted)

def load_hf_model(path):
    try:from transformers import AutoModelForCausalLM,AutoTokenizer
    except ImportError as e: raise RuntimeError('Install transformers to use --hf-model') from e
    tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(path,local_files_only=True,trust_remote_code=False,torch_dtype=torch.float32).eval().cpu()
    return model,tokenizer

def run_hf_decode(hf, prompt, sampler, tokens,seed,top_k,top_p,temp):
    model,tokenizer=hf
    ids=tokenizer.encode(prompt,return_tensors='pt')
    rng=np.random.default_rng(seed)
    gen=[];pre_ms=0.;forward_ms=0.;sample_ms=0.;cache=None
    with torch.inference_mode():
        t0=time.perf_counter()
        out=model(input_ids=ids,use_cache=True)
        cache=out.past_key_values
        pre_ms=(time.perf_counter()-t0)*1000
        logits=out.logits[0,-1]
        b=time.perf_counter()
        for i in range(tokens):
            t=time.perf_counter()
            token=sampler.sample(logits,top_k,top_p,temp,float(rng.random()))
            sample_ms+=(time.perf_counter()-t)*1000
            gen.append(token)
            if i+1==tokens:break
            t=time.perf_counter()
            out=model(input_ids=torch.tensor([[token]]),past_key_values=cache,use_cache=True)
            cache=out.past_key_values;logits=out.logits[0,-1]
            forward_ms+=(time.perf_counter()-t)*1000
        total_ms=(time.perf_counter()-b)*1000
    return dict(tokens=tokens,prefill_ms=pre_ms,total_ms=total_ms,model_ms=forward_ms,
                sampler_ms=sample_ms,tokens_per_second=tokens/(total_ms/1000),
                token_ids=gen,output=tokenizer.decode(gen,skip_special_tokens=False))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',choices=CONFIGS,default='dense-small')
    ap.add_argument('--checkpoint',help='Local .pt model weights for the selected demo architecture')
    ap.add_argument('--hf-model',help='Local Transformers-compatible pretrained checkpoint directory')
    ap.add_argument('--prompt',default='Explain how a stable sort works in simple terms.')
    ap.add_argument('--tokens',type=int,default=32)
    ap.add_argument('--rounds',type=int,default=3)
    ap.add_argument('--top-k',type=int,default=40)
    ap.add_argument('--top-p',type=float,default=.95)
    ap.add_argument('--temperature',type=float,default=.8)
    ap.add_argument('--methods',default='apex,torch_fast,torch,cpp_reference')
    ap.add_argument('--json-out')
    args=ap.parse_args()
    if args.tokens<1 or args.rounds<1: ap.error('tokens and rounds must be positive')
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    m=create_model(args.model,args.checkpoint) if not args.hf_model else None
    hf=load_hf_model(args.hf_model) if args.hf_model else None
    methods={'apex':ApexSampler(strategy=0),'cpp_reference':ApexSampler(strategy=1),'torch':TorchSampler(),'torch_fast':TorchFastSampler()}
    report={'model':args.hf_model or args.model, 'pretrained':bool(args.hf_model or args.checkpoint),
            'checkpoint':args.checkpoint,'torch':torch.__version__,
            'vocab_size':(m.config[0] if m else None), 'tokens':args.tokens,'rounds':args.rounds,'results':{}}
    names=args.methods.split(',')
    if any(name not in methods for name in names):ap.error('unknown sampler')
    all_runs={name:[] for name in names}
    # Prefill and warm each implementation before the measured, rotated rounds.
    for name in names:
        if m is None:run_hf_decode(hf,args.prompt,methods[name],min(8,args.tokens),815,args.top_k,args.top_p,args.temperature)
        else:run_decode(m,methods[name],min(8,args.tokens),815,args.top_k,args.top_p,args.temperature)
    for repeat in range(args.rounds):
        order=names[repeat % len(names):]+names[:repeat % len(names)]
        for name in order:
            sampler=methods[name]
            if m is None:
                result=run_hf_decode(hf,args.prompt,sampler,args.tokens,817+repeat,args.top_k,args.top_p,args.temperature)
            else:
                result=run_decode(m,sampler,args.tokens,817+repeat,args.top_k,args.top_p,args.temperature)
            all_runs[name].append(result)
    for name in names:
        runs=all_runs[name]
        mid=sorted(runs,key=lambda r:r['total_ms'])[len(runs)//2]
        report['results'][name]={'median_total_ms':mid['total_ms'],
               'median_tokens_per_sec':mid['tokens_per_second'],'median_model_ms':mid['model_ms'],
               'median_sampler_ms':mid['sampler_ms'], 'median_token_ids':mid['token_ids'],
               'runs':[{'total_ms':r['total_ms'],'tps':r['tokens_per_second']} for r in runs]}
    main_ids=report['results'].get('cpp_reference',{}).get('median_token_ids')
    if main_ids is not None:
        report['matching_reference']={k:v['median_token_ids']==main_ids for k,v in report['results'].items()}
        # Persist a per-seed trace parity check, not only median-run alignment.
        ref_runs=all_runs.get('cpp_reference',[])
        report['all_seeds_match_reference']={k: all(a['token_ids']==b['token_ids'] for a,b in zip(runs,ref_runs)) for k,runs in all_runs.items()}
    print(json.dumps(report,indent=2))
    if args.json_out:Path(args.json_out).write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
