---
title: Limitations
description: What Modeldiffr does not do, stated plainly.
---

# Limitations

What Modeldiffr does not do, stated plainly.

!!! warning

    The built in `quick` suite is a smoke test that only catches big drops. Use `lite`, `standard` or `full` for a real decision. The anomaly scan makes no claim about real models until its accuracy on a public zoo is published.

## Statistics

* "Within noise" means no evidence of a change at this sample size. It does not prove nothing changed. Check the smallest detectable change in the plan, or run `modeldiffr power`.
* The power estimate assumes the two models' per question results are correlated at 0.5.
* A real change shows that something moved, not why.

## Benchmarks and backends

* Both models are in memory at the same time. Two 7B models in bfloat16 need about 28 GB of GPU memory before activations.
* The vLLM and llama.cpp backends are tested in CI against stand in engines, not real GPUs. Please report anything that acts differently on real hardware.
* Hosted APIs rarely return prompt log probabilities, so multiple choice tasks need the `hf`, `vllm` or `llamacpp` backends, or a vLLM server.
* The default refusal detector uses keywords. Measure it, or a classifier, on your own labeled replies with `modeldiffr refusal-eval` before you rely on refusal metrics.
* IFEval checks are reimplemented and strict only. `language:response_language` needs `langdetect`.
* `humaneval` runs code the model wrote, with resource limits but without network isolation.
* `output_divergence_kl` needs the same vocabulary in both models. Pairs from different families skip it with a note.
* A base model without a chat template is compared with its instruct version through one shared template when the tokenizers match. Otherwise part of the difference is the prompt format, and the report says so.

## Proof

* A report that passes `verify` is consistent and tied to exact model files. It does not prove the audit was really run. A signature says who vouches for it, a timestamp says when, and rerunning is the only way to check the results themselves.
* Rerunning on different hardware can change log probabilities in the last digits, so `results_root` can differ while `audit_id` stays the same.
* Fingerprinting reads every weight file once. `--no-weight-hash` skips that for very large models, and the report says so.
* Sigstore and the Ethereum Attestation Service are tested with their real client libraries offline. The live services are not called in CI.
* A safetensors model and a GGUF build have no tensor level diff, because their tensor names and encodings differ.

## Layer by layer, features and causal tests

* They need the transformers backend and the same tokenizer in both models. GGUF builds are not supported here yet.
* The weights view says whether a tensor changed, not by how much.
* `layers` results have no confidence ranges yet, and are not saved as a verifiable file.
* Results describe only the text you give. Pick a corpus close to what the derivative was trained on.
* A crosscoder sees one layer, and finds only features the corpus triggers.
* Feature classes come from fixed thresholds. Features near a threshold could fall either way.
* Labels are written by a language model and are unverified.
* Causal shares use multiple choice questions only, one layer at a time.
* Crosscoder training is exact for a seed on CPU. On GPU two runs can differ slightly, so publish `crosscoder.safetensors`.

## Anomaly scan

* A flag is a lead to look into. Fine tunes change behavior on some inputs on purpose.
* No flag does not prove a model is clean. Triggers longer than the search length, or behavior that needs several chat turns, are outside what the scan tries.
* Rates measured on a zoo of small models with simple triggers do not automatically carry over to large models or to triggers built to avoid the scan.

## Formats

* Report schema 0.3 is the 1.0 candidate. Until 1.0 the formats may still change. Older reports always keep verifying. See [Schemas and compatibility](reference/compatibility.md).