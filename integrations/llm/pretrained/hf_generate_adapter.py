"""Optional Transformers.generate() token-selection hook.

This adapter is for compatibility with the public Transformers logits-processor
interface. Performance-sensitive use should prefer pretrained_engine.py's
manual cached decode loop, which does not allocate a masked vocabulary tensor.
"""
from __future__ import annotations

import numpy as np
import torch
from pretrained_engine import ApexSelector


class ApexForceTokenProcessor:
    """A LogitsProcessor-compatible callable that forces the APEX sampled token.

    Pass do_sample=False to model.generate(), and do NOT combine this processor
    with standard temperature/top-k/top-p processors. APEX processes the entire
    input logits itself. It supports batch > 1 with independent RNG streams.

    The CPU native selector incurs transfer overhead on GPU logits. Outputs
    are deliberately generated through Transformers' public generate path.
    """
    def __init__(self, *, top_k=40, top_p=.95, temperature=.8, seed=43, library=None):
        self.k = top_k
        self.p = top_p
        self.temperature = temperature
        self.seed = seed
        self.sampler = ApexSelector(library)
        self._rng = None
        self._rows = None

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        n, vocab = scores.shape
        if self._rows != n:
            self._rows = n
            self._rng = [np.random.default_rng(self.seed+i) for i in range(n)]
        selected = [
            self.sampler.select(scores[i], self.k, self.p, self.temperature,
                                float(self._rng[i].random()))
            for i in range(n)
        ]
        # Returning masked logits is required by Transformers' public API.
        # This is not the most efficient sampler integration (adds a scatter).
        out = torch.full_like(scores, -float('inf'))
        for i, chosen in enumerate(selected):
            out[i, chosen] = 0.0
        return out


def hf_generate_apex(model, input_ids: torch.LongTensor, *, attention_mask=None,
                     top_k=40, top_p=.95, temperature=.8, seed=43,
                     max_new_tokens=32, library=None):
    """Run actual HF model.generate() with APEX controlling token selection."""
    from transformers import LogitsProcessorList
    process = ApexForceTokenProcessor(
        top_k=top_k, top_p=top_p, temperature=temperature,
        seed=seed, library=library,
    )
    return model.generate(input_ids=input_ids, attention_mask=attention_mask,
                          do_sample=False, num_beams=1,
                          logits_processor=LogitsProcessorList([process]),
                          max_new_tokens=max_new_tokens,
                          pad_token_id=getattr(model.config, 'eos_token_id', None))
