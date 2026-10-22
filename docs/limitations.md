---
title: Limitations
description: What Modeldiffr does not do, layer by layer, stated plainly.
---

# Limitations

What Modeldiffr does not do, layer by layer, stated plainly.

!!! warning

    The built in `quick` suite is a smoke test that catches large regressions. Use `lite`, `standard` or `full` for a release decision. The anomaly scan makes no claim about real models until its rates on a public zoo are published.

## Statistics

* A metric reported as within noise means no evidence of change at this resolution, not proof of no change. Check the detectable change in the plan, or run `modeldiffr power`.
* Power estimates assume a correlation of 0.5 between the two models' per item results.
* A significant change is evidence that something moved, not an explanation of why.

## Benchmarks and backends

* Both models are held in memory at once. Two 7B models in bfloat16 need roughly 28 GB of accelerator memory before activations.
* The vLLM and llama.cpp backends are tested in CI against stand in engines, not real GPUs. Please report anything that behaves differently on real hardware.
* Hosted APIs rarely return prompt log probabilities, so multiple choice tasks need the `hf`, `vllm` or `llamacpp` backends or a vLLM server.
* The default refusal detector is keyword based. Measure it, or a classifier, on your own labeled responses with `modeldiffr refusal-eval` before relying on refusal metrics.
* IFEval checks are reimplemented and strict only; `language:response_language` needs `langdetect`.
* `humaneval` runs model written code with resource limits but without network isolation.
* `output_divergence_kl` needs identical vocabularies; cross family pairs skip it with a note.
* A base model without a chat template is compared with its instruct derivative through one shared template when the tokenizers match; otherwise part of the difference is the prompt format, and the report says so under comparability.

## Proof

* A report that passes `modeldiffr verify` is internally consistent and tied to exact model files. It does not prove the audit was run as recorded. A signature says who vouches for it; a timestamp says when; rerunning the audit is the only way to check the results themselves.
* Rerunning on different hardware can change log probabilities in the last digits, so `results_root` can differ while `audit_id` stays the same.
* Fingerprinting reads every weight file once. `--no-weight-hash` skips it for very large models, and the report then says so.
* Sigstore and the Ethereum Attestation Service are tested against their real client libraries offline; the live services are not called in CI.
* Between a safetensors model and a GGUF build there is no tensor level diff, because names and encodings differ.

## Representational and causal layers

* They need the transformers backend and the same tokenizer in both models.
* A crosscoder sees one layer, and finds only features the corpus exercises.
* Feature classes come from fixed thresholds on decoder norms; features near a threshold could fall either way.
* Labels are written by a language model and are unverified.
* Causal shares are measured on multiple choice items only, one layer at a time.
* Crosscoder training is deterministic on the CPU for a seed; on a GPU two runs can differ slightly, so publish `crosscoder.safetensors`.

## Anomaly scan

* A flag is a lead to investigate. Fine tunes legitimately change behavior on some inputs.
* No flag does not show that a model is free of hidden behavior. Triggers longer than the search length, or behavior that needs a multi turn context, are outside what the scan tries.
* Rates measured on a zoo of small models with simple triggers do not transfer automatically to large models or to triggers designed to evade the scan.

## Formats

* Report schema 0.3 is the 1.0 candidate. Until 1.0, formats may still change; older reports always keep verifying. See [Schemas and compatibility](reference/compatibility.md).
