---
title: Roadmap
description: Every phase from preview to v1.0, what is shipped, and what is not claimed yet.
---

# Roadmap

Every phase from preview to v1.0, what is shipped, and what is not claimed yet.

## Where we are

| Phase | Release | Status |
| --- | --- | --- |
| 0. Foundation | 0.1 | Shipped |
| 1. Trustworthy core | 0.2 | **Shipped** |
| 2. Behavioral layer MVP | 0.3 | Next |
| 3. Proof, signing and integrations | 0.4 | Planned |
| 4. Public audits and launch | 0.5 | Planned |
| 5. Representational layer | 0.6 | Planned |
| 6. Causal layer | 0.7 | Planned |
| 7. Anomaly scan | 0.8 | Research |
| 8. v1.0 and technical report | 1.0 | Planned |

## What v1.0 means

A developer runs one command on one GPU and gets, for any base and derivative pair from the Qwen, Llama, Gemma or Mistral families:

1. What changed in capability, safety, calibration, instruction following, multilinguality and output distribution, each with a paired interval corrected for multiple comparisons.
2. Which internal features are new, lost or shifted, with unverified labels.
3. How much of each behavioral change those features explain.
4. Suspicious behavior on rare inputs, with the scan's measured false positive rate next to it.
5. A signed, content addressed proof of exactly what was compared, which anyone can check with `modeldiffr verify`.

Measured exit criteria: an identical model shows no change in 50 of 50 seeded runs; at least 95% of planted regressions above the minimum effect are found; the anomaly scan's detection and false positive rates are published on at least 20 test models; at least 25 public audits are published; a technical report is on arXiv.

## Phase 0: Foundation (0.1, shipped)

* [x] Public repository, Apache 2.0 license, contribution and security policies
* [x] Behavioral smoke suite with confidence intervals
* [x] HTML and JSON reports
* [x] CI gate mode
* [x] Unit tests and CI on Python 3.10 to 3.12
* [x] PyPI release workflow

## Phase 1: Trustworthy core (0.2, shipped)

Every report is reproducible and provably refers to exact models.

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

## Phase 2: Behavioral layer MVP (0.3, next)

A behavioral audit people would use for a release decision.

* [ ] Suite registry with pinned datasets, item hashes and quick, standard and full sizes
* [ ] Adapters for EleutherAI lm evaluation harness and UK AISI Inspect tasks
* [ ] Suites: MMLU, ARC, HellaSwag, GSM8K, IFEval, XSTest and OR Bench, HarmBench or StrongREJECT, TruthfulQA, MGSM, HumanEval, long context needle
* [ ] vLLM backend for 7B to 32B models
* [ ] llama.cpp backend for GGUF quantized models, with GGUF fingerprints
* [ ] OpenAI compatible API backend for behavioral metrics
* [ ] Small validated refusal classifier, with its accuracy in every report
* [ ] Harmful compliance and calibration (expected calibration error) metrics
* [ ] Benjamini Hochberg correction across metrics, minimum effect sizes, and a power estimate before running
* [ ] GPU hour estimate printed before an audit starts
* [ ] Colab notebook for the quick suite on a free GPU

## Phase 3: Proof, signing and integrations (0.4)

Audits become evidence that tools and people can check.

* [ ] Sigstore signing (keyless with OpenID Connect, or an offline Ed25519 key)
* [ ] in toto attestation with a published predicate type, usable by cosign and policy engines
* [ ] Rekor transparency log inclusion check in `verify`
* [ ] Verification of OpenSSF model signing signatures on audited repos
* [ ] Optional public timestamps: OpenTimestamps on Bitcoin, Ethereum Attestation Service on an L2, batched so one anchor covers many audits. Only hashes go on chain
* [ ] Commit and reveal for private holdout suites
* [ ] GitHub Action that gates checkpoints and uploads a signed report
* [ ] Hugging Face integration: audit from a Hub URL, upload the report, model card badge
* [ ] AI bill of materials export (CycloneDX ML BOM, SPDX 3 AI profile)

## Phase 4: Public audits and launch (0.5)

* [ ] Positive controls: pairs with planted regressions, all found
* [ ] Ten signed public audits: official quants, popular fine tunes, merges, abliterated models
* [ ] A public registry where anyone can verify a listed audit in the browser
* [ ] Launch write up on the most significant finding outside noise
* [ ] Free signed audits offered to popular quantizers and fine tuners

## Phase 5: Representational layer (0.6)

* [ ] Activation capture for both models on identical tokens
* [ ] Difference of means and refusal direction extraction as a cheap first pass
* [ ] BatchTopK crosscoders and the delta crosscoder variant for narrow fine tunes
* [ ] Features classified as shared, base only, derivative only, or shifted
* [ ] Automatic labels, marked unverified, with the labeling prompt hashed into the proof
* [ ] Pretrained base side crosscoders on the Hub for popular models
* [ ] Fused Triton kernel for capture and steering

## Phase 6: Causal layer (0.7)

* [ ] Feature patching in both directions, reporting the share of each behavioral change explained, with an interval
* [ ] Steering checks that reproduce part of a change
* [ ] Each behavioral change linked to its top causal features in the report

## Phase 7: Anomaly scan (0.8)

* [ ] A published zoo of 20 deliberately backdoored and 20 clean small models with harmless triggers
* [ ] Rare input sweep and trigger search
* [ ] Detection and false positive rates published, whatever they are

## Phase 8: v1.0 and technical report

* [ ] Scale study of 25 or more popular derivative models, all signed
* [ ] Report schema 1.0 and attestation predicate 1.0 with a compatibility promise
* [ ] Technical report on arXiv
* [ ] At least two maintainers outside the founder

## Not claimed yet

!!! warning

    Modeldiffr does not yet detect backdoors or hidden behaviors. That claim will only be made after Phase 7 validation is published. The quick suite is a smoke test, not a benchmark. A verified report proves consistency and the exact model files, not that the author ran the audit honestly; signing in Phase 3 adds accountability.

## Acknowledgements

The representational layer builds on crosscoder based model diffing, introduced in *Sparse Crosscoders for Cross Layer Features and Model Diffing* (Lindsey et al., Anthropic, 2024), and on the follow up research it inspired. Behavioral evaluation draws on open harnesses such as EleutherAI's lm evaluation harness and UK AISI's Inspect. The proof layer follows RFC 8785 and RFC 6962 and is designed to interoperate with Sigstore and OpenSSF model signing.
