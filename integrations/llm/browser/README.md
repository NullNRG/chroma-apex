# Browser Inference Lab

The browser-native benchmark is implemented in [index.html](index.html). It runs as a standalone HTML file with local APEX JS and UI bundled; Transformers.js 4.3.2 and pretrained ONNX weights are downloaded on demand by the user's browser.

## Models and backends

| Preset | ONNX model | Format |
|---|---|---|
| SmolLM2-135M-Instruct | [HuggingFaceTB/SmolLM2-135M-Instruct](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct) | q4f16 WebGPU / q8 WASM |
| Gemma 3 270M Instruct | [onnx-community/gemma-3-270m-it-ONNX](https://huggingface.co/onnx-community/gemma-3-270m-it-ONNX) | q4f16 WebGPU / q8 WASM |
| Gemma 3 270M base | [onnx-community/gemma-3-270m-ONNX](https://huggingface.co/onnx-community/gemma-3-270m-ONNX) | q4f16 WebGPU / q8 WASM |

## Execution

Open the [standalone page](index.html) from a secure HTTPS origin, or serve its directory locally:

```sh
python3 -m http.server 8000
```

Visit http://localhost:8000/index.html. Load the selected model, enter a prompt and sampling settings, and choose **Benchmark all 3 modes**. Results can be exported as JSON for reproducibility.

The three modes are:
1. **APEX:** Reads genuine next-token model logits using the public Transformers.js custom logits processor. It selects with stable float32 radix sorting (unrestricted nucleus), bounded top-k heap selection, or a linear untruncated sampler. It then masks all other tokens.
2. **Reference:** Same custom processor hook, same seeded random draws, using a full JavaScript vocabulary sort.
3. **Native:** Uses the Transformers.js default sampler without CPU-side custom masking.

The first two modes should emit identical token IDs. Native tokens per second are approximate because the pipeline may not expose the exact number of generated tokens after EOS.

## Testing and evidence

The APEX token selection code passed **76,320 local deterministic assertions** on its standalone module, including nonfinite inputs, ties, top-k, top-p, temperature, deterministic sampling and mock processor invocation. A headless Chromium integration test passed with no JavaScript errors, working synthetic-logit benchmark and no mobile horizontal overflow.

An illustrative headless Chromium CPU selection run (milliseconds per decision):

| Vocab | Sampling | APEX | Full-sort reference |
|---:|---|---:|---:|
| 49,152 | top-40 | 0.24 | 16.85 |
| 49,152 | top-p .90 | 2.85 | 18.27 |
| 128,000 | top-40 | 0.64 | 45.40 |
| 128,000 | top-p .90 | 7.54 | 50.56 |

These are **synthetic logits**, not model inference measurements. The full-sort reference is deliberately less efficient than production native samplers. No pretrained checkpoints could be downloaded or run in the build container due blocked outbound model host access. Per-model tokens/sec results will only be produced by running this page on hardware with model access.

### Performance caution

For GPU-backed models, reading logits into JavaScript and applying a CPU mask can require device-to-host synchronization. APEX may therefore be slower end-to-end than the native GPU sampler even when its CPU sorting primitive is faster. Model weights have upstream licenses (including separate Gemma terms), and no weights or third-party runtime code is bundled in this repository.

The algorithms use established radix, heap and linear sampling primitives. This is a browser integration, not a new sorting complexity claim.
