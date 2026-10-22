---
title: Introduction
description: Know exactly what changed inside a model before you ship it.
---

# Introduction

Modeldiffr audits the difference between a **base** language model and a **derivative** of it: a fine tune, a quantized build, a merge, or an edited checkpoint. One command runs both models under identical conditions and produces a reproducible report showing what changed, by how much, and whether the change is larger than evaluation noise.

```bash
pip install "modeldiffr[hf]"
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct your-org/your-qwen-finetune
```

!!! note

    **Early preview (v0.3), Phases 1 and 2 shipped.** Thirteen standard benchmarks across capability, safety, calibration, instruction following, code and long context, four backends including GGUF, and every report fingerprinted and verifiable. Signing, representational diffing and causal checks are on the [roadmap](roadmap.md). Expect the report schema to change before v1.0.

## Why Modeldiffr

Hugging Face hosts hundreds of thousands of derivative models. A model card might say "fine tuned for medical Q&A" or "4 bit, near lossless", but nobody can cheaply check whether general capability dropped, whether safety behavior shifted, or whether a merge is actually better than its parents.

Benchmarks run by hand show that a score moved, not whether the move is real, and comparisons are often unfair because prompts, templates, or decoding settings differ between runs. Modeldiffr makes the comparison **fair**, **statistical**, and **repeatable**.

## What it measures today

<div class="grid cards" markdown>

-   **[capability_accuracy](concepts/metrics.md#capability-accuracy)**

    ---

    Multiple choice accuracy scored by log likelihood. Higher is better.

-   **[over_refusal_rate](concepts/metrics.md#over-refusal-rate)**

    ---

    Share of harmless but sensitive sounding prompts the model refuses. Lower is better.

-   **[output_divergence_kl](concepts/metrics.md#output-divergence-kl)**

    ---

    Mean KL divergence of next token distributions. Reported as changed, not good or bad.

</div>

Every metric is reported as a **paired delta with a 95% bootstrap confidence interval**. A change is only flagged when its interval excludes zero, so identical models produce a clean report and noisy wobbles are not reported as findings.

## Every report is evidence

Each audit hashes both models tensor by tensor, every question asked and every result, and gets an audit id computed before anything runs. Anyone can check a report without trusting its author:

```bash
modeldiffr verify report.json --models
```

The report also says exactly which tensors changed, so a "near lossless" quant that touched every layer, or a fine tune that replaced the embeddings, is visible before a single benchmark runs. See [Fingerprints and proof](concepts/proof.md).

## Start here

<div class="grid cards" markdown>

-   **[Verify a report](guides/verify.md)**

    ---

    Check that a report was not edited and matches the real model files.

-   **[Installation](installation.md)**

    ---

    Install the core package or the Hugging Face extra.

-   **[Quickstart](quickstart.md)**

    ---

    Run your first audit and read the report.

-   **[Use it as a CI gate](guides/ci_gate.md)**

    ---

    Block a checkpoint that changes significantly.

-   **[Report schema](reference/report_schema.md)**

    ---

    Every field in report.json.

</div>

## The four layers

Modeldiffr is designed as four layers. Layer 1 ships today.

| Layer | Question | Status |
| --- | --- | --- |
| 1. Behavioral diff | What changed in behavior? | v0.1 smoke suite shipped |
| 2. Representational diff | Where inside the model did it change? | Planned |
| 3. Causal diff | Does that internal change drive the behavior change? | Planned |
| 4. Anomaly scan | Is anything suspicious, such as behavior on rare inputs? | Research |
