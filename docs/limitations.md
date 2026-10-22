---
title: Limitations
description: What v0.1 does not do, stated plainly.
---

# Limitations

What v0.1 does not do, stated plainly.

!!! warning

    Modeldiffr v0.1 is a smoke test. It catches large regressions. It is not a substitute for full benchmarks.

## Small built in suite

The `quick` suite has 24 capability items, 20 over refusal prompts, and 12 divergence texts. With so few items, intervals are wide and only large changes reach significance. A metric reported as within noise means no evidence of change at this resolution, not proof of no change.

## Keyword refusal detector

`is_refusal` matches phrases such as "I cannot" or "I'm sorry, but" in the first 400 characters. It will:

* miss refusals phrased in other ways, or in other languages
* misread answers that begin with an apology but then help

## Memory

Both models are loaded at once on the same device. Two 7B models in bfloat16 need roughly 28 GB of accelerator memory before activations. Large models need a GPU.

## Tokenizer mismatch

`output_divergence_kl` requires identical vocabularies. Cross family comparisons, or derivatives that added tokens, skip it with a note.

## Chat templates

Over refusal generation uses each model's own chat template. A base model without a template falls back to `User: ...\nAssistant:`, which is a different prompt from the instruct template. Comparing a base model with its instruct derivative is therefore partly a comparison of prompt formats. Chat template mismatch detection is on the [roadmap](roadmap.md).

## What a change means

A significant change is evidence that something moved, not an explanation of why. Explaining the why is what the representational and causal layers are for.

## Not claimed

* Modeldiffr does not yet detect backdoors or hidden behaviors. That claim will only be made after measured validation.
* The report schema will change before v1.0.

## Proof and fingerprints

* A report that passes `modeldiffr verify` is internally consistent and tied to exact model files. It does not prove the author ran the audit honestly. Signing arrives in Phase 3.
* GGUF files are not fingerprinted yet; they arrive with the llama.cpp backend.
* Fingerprinting reads every weight file once. For very large models, `--no-weight-hash` skips it, and the report then says so.
* Rerunning on different hardware can change log probabilities in the last digits, so `results_root` can differ while `audit_id` stays the same.
