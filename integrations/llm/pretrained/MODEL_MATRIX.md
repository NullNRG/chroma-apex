# Pretrained Model Test Matrix

The engine accepts any compatible Hugging Face causal-LM checkpoint. Reference checkpoints for the current evaluation are listed below. **None were executed in the offline integration environment.**

| Checkpoint | Approximate scale | Architecture | Known numeric vocabulary | Suggested evaluation |
|---|---:|---|---:|---|
| [TinyStories-1M](https://huggingface.co/roneneldan/TinyStories-1M) | ~1M non-embedding / small | GPT-Neo | 50,257 | CPU top-40 and top-k=0 nucleus |
| [TinyStories-33M](https://huggingface.co/roneneldan/TinyStories-33M) | ~33M | GPT-Neo | 50,257 | CPU forward-dominated comparison |
| [DistilGPT2](https://huggingface.co/distilbert/distilgpt2) | ~82M | GPT-2 | 50,257 | Optimized top-k baseline, seeded text continuation |
| [SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct) | 135M | Llama | 49,152 | GQA, larger forward pass, optional GPU |

## Evaluation protocol

1. Load one **real checkpoint** with `AutoModelForCausalLM.from_pretrained` and its actual tokenizer. Do not substitute random model weights.
2. Use the same initial prompt, numerical precision, model, device, KV-cache structure and fixed uniforms for every backend.
3. Run warmup passes and alternate the APEX, PyTorch optimized, and exact-reference selectors across repetitions.
4. Compare generated token IDs; report differences, not just text resemblance.
5. Report separately prefill, forward computation, sampling overhead and end-to-end generation throughput.
6. On GPU, include device-to-host transfer time for the native APEX path.
7. Measure default `top_k=40, top_p=.95` separately from `top_k=0, top_p=.95` because the optimization trade-offs reverse.

Even a statistically significant token-selection gain is not an LLM throughput gain unless full generation is faster. No claim is made about model quality or GPU performance.
