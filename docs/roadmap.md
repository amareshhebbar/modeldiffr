---
title: Roadmap
description: Every phase from preview to v1.0, what is done, and what is still pending.
---

# Roadmap

Every phase from preview to v1.0, what is done, and what is still pending.

## Where we are

All the code for every phase is written and tested. What is left before 1.0 is mostly **running it at scale and publishing the results**, plus a list of engineering improvements. Both are listed in [Still pending](#still-pending).

| Phase | Release | Status |
| --- | --- | --- |
| 0. Foundation | 0.1 | Done |
| 1. Trustworthy core | 0.2 | Done |
| 2. Benchmarks | 0.3 | Done, a few extras open |
| 3. Signing and integrations | 0.4 | Done |
| 4. Public audits | 0.5 | **Tools done, audits not yet run and published** |
| 5. Layer by layer and features | 0.6 | **Done, improvements open** |
| 6. Causal tests | 0.7 | Done |
| 7. Anomaly scan | 0.8 | **Tools done, accuracy not yet published** |
| 8. Toward v1.0 | 0.9 | **Tools done, study and paper not yet published** |
| v1.0 | 1.0 | When the exit goals below are met |

## What v1.0 means

A developer runs one command on one GPU and gets, for any base and derivative pair from the Qwen, Llama, Gemma or Mistral families:

1. What changed in capability, safety, calibration, instruction following, other languages and output distribution, each with a paired range corrected for many metrics.
2. Which layers changed, and which internal features are new, lost or shifted, with unverified labels.
3. How much of each behavior change those features explain.
4. Suspicious behavior on rare inputs, with the scan's measured false alarm rate next to it.
5. A signed proof of exactly what was compared, which anyone can check with `modeldiffr verify`.

Measured exit goals:

* Two identical models show no change in 50 of 50 seeded runs.
* At least 95% of planted changes above the minimum size are found.
* The anomaly scan's hit rate and false alarm rate are published on at least 20 test models.
* At least 25 public audits are published.
* A technical report is on arXiv.

## Still pending

### Blocking v1.0

These need GPU time and publishing, not new code.

| Item | Phase | What is needed |
| --- | --- | --- |
| Control study and the eleven ready audits | 4 | Run `examples/public_audits.yaml` and `examples/controls.yaml` on a GPU, sign every report, publish the registry |
| Scale study of 25 or more popular derivatives | 8 | Pick the models, run `standard`, sign, publish with `modeldiffr study` tables |
| Public backdoor zoo | 7 | Build 20 backdoored and 20 clean small public models, run `zoo eval`, publish the rates whatever they are |
| Technical report on arXiv | 8 | Fill `paper/main.tex` with the study and zoo numbers, submit |
| Launch write up | 4 | One post on the most important finding outside noise |
| Two maintainers outside the founder | 8 | Recruit from contributors |

### Layer by layer and features

| Item | Why it matters |
| --- | --- |
| Save `layers` output as `layers.json` and `layers.html` with its own id, result hash, `verify` support and registry page | Today `layers` only prints to the terminal. Every other tool writes a verifiable file |
| Confidence ranges per layer (bootstrap over texts) | Every other number in Modeldiffr has a range. A layer number without one cannot say whether 0.98 CKA is a real change |
| A noise floor per layer, from comparing the base with itself in a different dtype | Tells you how much change is just precision, which matters most for quants |
| Size of the weight change per tensor and per layer (relative norm of the difference) | The weights view says only changed or unchanged. A quant and a full fine tune both show "every tensor changed" |
| A larger built in corpus for `layers` | The built in text is under 100 short texts. Fine for a smoke test, thin for a decision |
| Per layer chart in the HTML pages | The pattern across layers is the main thing to read, and a table hides it |
| Layer comparison for GGUF builds | Quants are the most common derivative, and today `layers` needs transformers on both sides |
| Layer comparison across different tokenizers, by aligning shared text spans | Today texts that tokenize differently are skipped |
| Pretrained crosscoders on the Hub for popular pairs | Training takes hours, and most people audit the same popular pairs |
| Fused Triton kernel for capture and steering | Speed and memory on large models |

### Causal tests

| Item | Why it matters |
| --- | --- |
| Interventions on generation tasks with a judge | Refusal, math and instruction following are generation tasks, and causal tests cover only multiple choice today |
| Batched interventions | Runs one sequence at a time, which is slow on large models |
| Patching several layers together | A change spread over layers shows up only as partial shares today |

### Benchmarks and backends

| Item | Why it matters |
| --- | --- |
| Adapters for EleutherAI lm evaluation harness and UK AISI Inspect tasks | Reuse hundreds of existing tasks |
| A default refusal classifier tested on a published labeled set, with its accuracy in every report | The keyword detector is rough |
| Measured GPU hours per suite on common GPUs | People need cost before they commit |
| vLLM and llama.cpp tested on real GPUs in CI | Today they are tested against stand in engines |
| Output divergence on vLLM and API backends | These backends do not return full next token distributions, so the metric is unavailable there |

### Proof

| Item | Why it matters |
| --- | --- |
| Sigstore and EAS tested against the live services in CI | Today they are tested offline with the real libraries |

### Docs

| Item | Why it matters |
| --- | --- |
| Rewrite the reference and guide pages in the same plain style as the concept pages | Reference pages are still dense flag tables |

## Phase 0: Foundation (0.1, done)

* [x] Public repository, Apache 2.0 license, contribution and security policies
* [x] Behavioral smoke suite with confidence intervals
* [x] HTML and JSON reports
* [x] CI gate mode
* [x] Unit tests and CI on Python 3.10 to 3.12
* [x] PyPI release workflow

## Phase 1: Trustworthy core (0.2, done)

Every report can be repeated and provably points to exact models.

* [x] Weight fingerprints: per tensor SHA 256 and a Merkle root that ignores sharding, for safetensors and PyTorch checkpoints
* [x] Tensor level diff in every report: which tensors changed, were added or removed
* [x] Tokenizer, vocabulary and chat template fingerprints
* [x] Comparability checks, and one shared template for generation prompts when templates differ
* [x] RFC 8785 canonical JSON and an audit id computed before anything runs
* [x] Merkle root over every per item result, and a statement hash over every claim
* [x] `modeldiffr verify`, offline and against real model files
* [x] `modeldiffr fingerprint` for a single model
* [x] Report schema 0.2 published as JSON Schema
* [x] Identical model control: 50 seeded runs, zero changes, in CI
* [x] Tamper tests and a CPU integration test with a real transformers model in CI
* [x] Docs moved to MkDocs on Netlify

See [Fingerprints and proof](concepts/proof.md).

## Phase 2: Benchmarks (0.3, done)

An audit good enough for a real release decision.

* [x] Suite registry with pinned datasets, item hashes, and `lite`, `standard` and `full` sizes; the built in `quick` suite kept
* [x] Tasks: MMLU, ARC Challenge, HellaSwag, TruthfulQA MC1, GSM8K, MGSM in ten languages, IFEval, XSTest safe and unsafe, OR Bench hard and toxic, HumanEval in a limited subprocess, long context needle, output divergence
* [x] Deterministic, nested item sampling, and offline data folders
* [x] Batched transformers backend, vLLM backend, llama.cpp backend for GGUF builds, OpenAI compatible API backend, and a different backend per model
* [x] GGUF fingerprints from quantized bytes, checked against the reference type table
* [x] Pluggable refusal detectors (keyword or any Hugging Face classifier) and `modeldiffr refusal-eval`
* [x] Harmful compliance and calibration (expected calibration error) metrics
* [x] Bootstrap p values, Benjamini Hochberg correction across metrics, minimum effect sizes and a negligible verdict
* [x] Power estimate for every task before running, `modeldiffr power`, and a run time estimate from timed calls
* [x] Colab notebook for the `lite` suite on a free GPU
* [x] Reports from 0.2 still verify
* [ ] Adapters for EleutherAI lm evaluation harness and UK AISI Inspect tasks
* [ ] A default refusal classifier validated on a published labeled set, with its accuracy in every report
* [ ] Measured GPU hours per suite on common GPUs, published here
* [ ] vLLM and llama.cpp backends exercised on real hardware in CI

## Phase 3: Signing and integrations (0.4, done)

Audits become evidence that tools and people can check.

* [x] Sigstore signing (keyless with OpenID Connect) and offline Ed25519 keys, both as DSSE envelopes
* [x] in toto Statement v1 with the predicate type `https://modeldiffr.dev/attestation/audit/v1`, bound to the report in `verify`
* [x] Rekor transparency log inclusion checked as part of Sigstore bundle verification
* [x] Verification of OpenSSF model signing signatures (`model.sig`) on audited models
* [x] Optional public timestamps: OpenTimestamps on Bitcoin (calendars batch many audits into one transaction) and the Ethereum Attestation Service on an L2. Only hashes go on chain
* [x] Commit and reveal for private holdout suites
* [x] GitHub Action that gates checkpoints, signs and uploads the report
* [x] Hugging Face integration: audit from a Hub URL, upload the report, model card badge
* [x] AI bill of materials export (CycloneDX 1.6, SPDX 3.0.1 AI profile)
* [ ] Sigstore and EAS exercised against the live services in CI (tested against the real libraries offline today)

See [Attestations](concepts/attestation.md).

## Phase 4: Public audits (0.5, tools done)

* [x] Positive controls: `modeldiffr controls make` plants identity, noise, scale, zero and pruning changes, reproducibly
* [x] Batch audits from YAML or JSON with resume, scored controls, detection and false positive rates
* [x] A public registry where anyone can verify a listed audit in the browser, including Ed25519 signatures
* [x] A ready spec for eleven public audits: official GGUF quants, abliterated models, instruction tunes, a distillation and two controls
* [ ] Run the control study and the eleven audits on a GPU and publish them, signed
* [ ] Launch write up on the most significant finding outside noise
* [ ] Free signed audits offered to popular quantizers and fine tuners

See [Positive controls](guides/controls.md), [Batch audits](guides/batch.md) and [Public registry](guides/registry.md).

## Phase 5: Layer by layer and features (0.6, done)

* [x] Activation capture for both models on identical tokens, with skipped texts counted
* [x] Layer by layer statistics: linear CKA, cosine, relative change, mean shift, norm ratio (`modeldiffr layers`)
* [x] Difference of means directions compared across models, with separation along the base direction (`modeldiffr directions`)
* [x] BatchTopK crosscoders and the delta variant for narrow fine tunes (`modeldiffr features`)
* [x] Features classified as shared, base only, derivative only, shifted or dead, with fixed published thresholds
* [x] Top activating contexts and automatic labels, marked unverified, with the labeling prompt hashed into the manifest
* [x] `features.json` with its own id, result hash and crosscoder weight hash, checked by `modeldiffr verify`, linked to an audit and shown in the registry
* [ ] Saved, verifiable `layers.json` and `layers.html`, with confidence ranges per layer
* [ ] Size of the weight change per tensor and per layer, not only changed or unchanged
* [ ] Pretrained crosscoders on the Hub for popular model pairs
* [ ] Fused Triton kernel for capture and steering

See [Layer by layer comparison](concepts/layer_by_layer.md) and [Features](concepts/representational.md).

## Phase 6: Causal tests (0.7, done)

* [x] Layer patching in both directions and crosscoder feature patching, reporting the share of the behavioral change reproduced, with a bootstrap interval
* [x] Steering checks along the mean activation difference
* [x] Feature attribution on task tokens, and the top features linked to the audit in `causal.json`
* [x] `causal.json` with its own id and result hash, checked by `modeldiffr verify`, shown in the registry
* [ ] Interventions on generation tasks with a judge

See [Causal tests](concepts/causal.md).

## Phase 7: Anomaly scan (0.8, tools done)

* [x] Rare input sweep with robust z scores (`modeldiffr scan`)
* [x] Gradient guided trigger search against a random trigger reference
* [x] Zoo builder with harmless triggers, blind model names and a separate answer key (`modeldiffr zoo make`)
* [x] Zoo evaluation with detection and false positive rates, Wilson intervals, AUCs and trigger recovery (`modeldiffr zoo eval`)
* [x] `scan.json` with its own id and result hash, checked by `modeldiffr verify`, shown in the registry
* [ ] A published zoo of 20 backdoored and 20 clean public small models, with rates, whatever they are

See [Anomaly scan](concepts/anomaly.md).

## Phase 8: Toward v1.0 (0.9, tools done)

* [x] `modeldiffr study` turns a folder of audits into tables by derivative kind and by metric, as Markdown, CSV, LaTeX and JSON
* [x] JSON Schemas for features, causal and scan files and for the attestation predicate, checked by `verify`
* [x] Report schema 0.3 declared the 1.0 candidate, with the [compatibility promise](reference/compatibility.md) written down
* [x] Governance, maintainers and release process documented
* [x] Technical report draft with methods written, in the docs and as LaTeX
* [ ] Scale study of 25 or more popular derivative models, all signed
* [ ] Technical report on arXiv
* [ ] At least two maintainers outside the founder

## v1.0

Released when every exit goal in [What v1.0 means](#what-v10-means) is met and published. Until then the version stays below 1.0, however complete the code is.

## Not claimed yet

!!! warning

    Modeldiffr does not claim to find backdoors or hidden behavior in real models. The scan comes with the tools to measure its own accuracy, and the claim will only be made, with the measured rates, after a zoo of 20 backdoored and 20 clean public models is published. The quick suite is a smoke test, not a benchmark. A verified report proves consistency and the exact model files, not that the author ran the audit honestly. A signature adds accountability, not proof of honest execution.

## Acknowledgements

The feature comparison builds on crosscoder model diffing from *Sparse Crosscoders for Cross Layer Features and Model Diffing* (Lindsey et al., Anthropic, 2024) and the research that followed it. The benchmark side learns from EleutherAI's lm evaluation harness and UK AISI's Inspect. The proof side follows RFC 8785 and RFC 6962 and works with Sigstore and OpenSSF model signing.