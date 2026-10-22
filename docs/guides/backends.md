---
title: Backends
description: Run models with transformers, vLLM, llama.cpp or any OpenAI compatible API.
---

# Backends

Run models with transformers, vLLM, llama.cpp or any OpenAI compatible API.

| Backend | Install | Good for | Divergence | Fingerprints |
| --- | --- | --- | --- | --- |
| `hf` (default) | `modeldiffr[hf]` | Anything transformers loads, CPU or GPU | Yes | Weights, tokenizer, template |
| `vllm` | `modeldiffr[vllm]` | 7B to 70B on GPU, much faster generation | No | Weights, tokenizer, template |
| `llamacpp` | `modeldiffr[llamacpp]` | GGUF quantized builds, CPU or GPU | Yes | GGUF tensors, vocabulary, template |
| `api` | core | Models behind an OpenAI compatible endpoint | No | None |

Choose one backend for both models with `--backend`, or one per model with `--base-backend` and `--derivative-backend`. Paths ending in `.gguf` pick `llamacpp` automatically.

## Transformers

```bash
modeldiffr audit Qwen/Qwen2.5-7B-Instruct org/qwen-ft --dtype bfloat16 --suite standard
```

Log likelihood calls and generations are batched (16 and 8 per batch). Batched and single calls agree to within 1e-4 on log probabilities, and greedy outputs are identical; this is tested in CI.

## vLLM

```bash
pip install "modeldiffr[vllm]"
modeldiffr audit org/base org/derivative --backend vllm --suite standard
```

Log likelihoods come from vLLM's prompt log probabilities and generations from greedy sampling. vLLM does not expose full next token distributions, so `output_divergence_kl` is skipped with a note. Both models are held on the GPU at once; use `--base-backend vllm --derivative-backend vllm` only when both fit.

## llama.cpp and GGUF

Audit a quantized build against its original:

```bash
pip install "modeldiffr[hf,llamacpp]"
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct ./qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --base-backend hf --suite lite --n-gpu-layers 0
```

A GGUF on the Hub can be named as `REPO:FILE`:

```bash
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B-Instruct-GGUF:qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --base-backend hf --derivative-backend llamacpp --suite lite
```

The chat template comes from the GGUF metadata. GGUF files are fingerprinted tensor by tensor from their quantized bytes, so two uploads of the same quant have the same root. Between a safetensors base and a GGUF derivative there is no tensor level diff, because names and encodings differ; the report says so.

Divergence between a transformers model and a GGUF model is computed only on texts that both tokenize to the same ids. Texts that tokenize differently are left out, and the metric is skipped if none remain.

`--n-ctx` sets the context window (default 4096) and `--n-gpu-layers` how many layers run on the GPU (default 0, CPU only).

## OpenAI compatible API

```bash
export MODELDIFFR_API_KEY=...
modeldiffr audit base-model-name tuned-model-name --backend api --api-base http://localhost:8000/v1 --suite lite --tasks gsm8k,ifeval,xstest_safe
```

Generation uses `/chat/completions` with temperature 0. Multiple choice tasks need prompt log probabilities from `/completions` with `echo` and `logprobs`, which vLLM's server provides and most hosted APIs do not; those tasks then stop with a clear error, so pick generation tasks with `--tasks`. The API key is read from `MODELDIFFR_API_KEY` or `OPENAI_API_KEY` and never written to the report.

## Write your own

Any object with the methods in the [Backend protocol](../reference/python/backend_protocol.md) works. Add `choice_logprobs_batch` and `generate_raw_batch` for speed, `fingerprint`, `render_chat` and `generate_raw` for proof and shared templates, `token_logprobs` for divergence across backends, and `max_context` for the needle task.
