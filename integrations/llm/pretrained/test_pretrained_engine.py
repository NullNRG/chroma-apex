import unittest
import sys
import time
from pathlib import Path
import numpy as np
import torch
from torch import nn

sys.path.insert(0,str(Path(__file__).resolve().parent))
from pretrained_engine import (ApexSelector,AdaptiveSelector,TorchExactSelector,TorchTopKSelector,
    decode_trace,benchmark_pretrained, sync_device)


class FakeOutput:
    def __init__(self,logits,past):self.logits=logits; self.past_key_values=past


class FakeHFDecoder(nn.Module):
    """A cache-aware decoder *test double*. NOT a pretrained model."""
    def __init__(self,vocab=768,hidden=96):
        super().__init__(); torch.manual_seed(120)
        self.embed=nn.Embedding(vocab,hidden)
        self.rnn=nn.GRU(hidden,hidden,batch_first=True)
        self.head=nn.Linear(hidden,vocab,bias=True)
        self.is_fake=True
        self.history=[]
    def forward(self,input_ids,attention_mask,past_key_values=None,use_cache=True):
        self.history.append(tuple(input_ids.shape))
        state=past_key_values
        z,state=self.rnn(self.embed(input_ids),state)
        return FakeOutput(self.head(z),state)


class PretrainedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        cls.native=ApexSelector()
        cls.exact=TorchExactSelector()
        cls.torch=TorchTopKSelector()

    def test_selection_parity(self):
        rng=np.random.default_rng(303)
        for n in (1, 3, 8, 32, 768, 8192, 50257):
            for k,p in ((1,1),(0,1),(40,.95),(10,.7),(0,.93)):
                if n<k and k>0: continue
                for seed in range(2):
                    a=rng.standard_normal(n).astype('f')
                    if n>8: a[0]=-float('inf')
                    if n>16: a[1]=float('nan')
                    if n>32: a[2]=a[3]
                    x=torch.from_numpy(a)
                    u=.1237 if seed==0 else .9142
                    result=self.native.select(x,k,p,.85,u)
                    expected=self.exact.select(x,k,p,.85,u)
                    self.assertEqual(result, expected, (n,k,p,u))

    def test_forward_steps_are_cached(self):
        model=FakeHFDecoder().eval()
        ids=torch.tensor([[11,17,23,29]])
        trace=decode_trace(model,ids,self.native,max_new_tokens=14,seed=44)
        self.assertEqual(len(trace.ids),14)
        self.assertEqual(model.history[0],(1,4))
        self.assertEqual(model.history[1:],[(1,1)]*13)
        self.assertGreater(trace.prefill_s,0)
        self.assertGreater(trace.selection_s,0)

    def test_identical_tokens_on_same_model(self):
        model=FakeHFDecoder(vocab=1024).eval()
        for seed in (3,13,42):
            args=dict(max_new_tokens=20,top_k=40,top_p=.95,temperature=.8,seed=seed)
            ref=decode_trace(model,torch.tensor([[2,6,8]]),self.exact,**args)
            apx=decode_trace(model,torch.tensor([[2,6,8]]),self.native,**args)
            top=decode_trace(model,torch.tensor([[2,6,8]]),self.torch,**args)
            self.assertEqual(ref.ids,apx.ids)
            self.assertEqual(ref.ids,top.ids)

    def test_adaptive_policy(self):
        selector=AdaptiveSelector()
        self.assertEqual(selector.route(torch.zeros(50257),40,.95,.8),'torch_optimized')
        self.assertEqual(selector.route(torch.zeros(50257),0,.95,.8),'apex')
        self.assertEqual(selector.route(torch.zeros(8192),40,.95,.8),'apex')
        self.assertEqual(selector.route(torch.zeros(50257),1,1,0),'torch_optimized')

    def test_generate_adapter(self):
        from hf_generate_adapter import ApexForceTokenProcessor
        model=FakeHFDecoder().eval()
        ids=torch.tensor([[5,6,7]])
        logits=model(input_ids=ids,attention_mask=torch.ones_like(ids)).logits[:,-1]
        processor=ApexForceTokenProcessor(seed=13)
        masked=processor(ids,logits)
        self.assertEqual(masked.shape,logits.shape)
        self.assertEqual(torch.isfinite(masked).sum().item(),1)
        masked2=processor(ids,logits)
        self.assertEqual(torch.isfinite(masked2).sum().item(),1)


if __name__=='__main__':unittest.main()
