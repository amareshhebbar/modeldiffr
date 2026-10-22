---
title: Changelog
description: Release history. The project uses Semantic Versioning.
---

# Changelog

Release history. The project uses Semantic Versioning.

## 0.7.0

*October 2026*

### Phase 6: causal layer

**Added**

* `modeldiffr causal` patches a layer, a set of crosscoder features or a steering direction from the derivative into the base and reports how much of the behavioral change follows, with an interval. See [Test what drives a change](guides/causal.md).
* Causal files have their own id and hashes and are checked by `modeldiffr verify`.

## 0.6.0

*October 2026*

### Phase 5: representational layer

**Added**

* `modeldiffr layers` compares hidden states layer by layer.
* `modeldiffr directions` compares difference of means directions, such as a refusal direction.
* `modeldiffr features` trains a BatchTopK crosscoder and lists new, lost and shifted features with examples and optional unverified labels. See [Find changed features](guides/features.md).
* Features files have their own id and hashes and are checked by `modeldiffr verify`.

## 0.5.0

*October 2026*

### Phase 4: public audits, tooling

**Added**

* `modeldiffr controls make` writes copies of a model with planted changes (identity, noise, scale, zero, pruning). See [Positive controls](guides/controls.md).
* `modeldiffr batch` runs many audits from one file, resumes after failures and scores planted changes. See [Batch audits](guides/batch.md).
* `modeldiffr registry build` publishes audits as a static site where every visitor's browser recomputes the hashes and checks Ed25519 signatures. See [Public registry](guides/registry.md).
* Example specs for a control study and eleven public audits.
* Extra `batch`.

## 0.4.0

*October 2026*

### Phase 3: proof, signing and integrations

**Added**

* Every report can be signed as an in toto Statement v1 with predicate type `https://modeldiffr.dev/attestation/audit/v1`. See [Attestations](concepts/attestation.md).
* `modeldiffr keygen` and `modeldiffr sign`: Ed25519 keys or Sigstore keyless signing, both as DSSE envelopes. `audit --sign-key` and `audit --sigstore` sign right after the run.
* `verify --key`, `--identity`, `--issuer`, `--staging` and `--rpc`. Signatures must match the report's audit id, results root, statement hash and verdict.
* OpenSSF model signing check for `model.sig` in audited models.
* `modeldiffr anchor ots`, `anchor upgrade` and `anchor eas`. Only hashes are published.
* `modeldiffr commit` and `modeldiffr reveal` for private holdout suites.
* `modeldiffr bom` for CycloneDX 1.6 and SPDX 3.0.1.
* `modeldiffr hub push`, `modeldiffr badge`, and Hub URLs as model references.
* A GitHub Action that audits, gates, signs and uploads the report.
* Extras `sign` and `anchor`.

## 0.3.0

*October 2026*

### Phase 2: behavioral layer

**Added**

* Suites `lite`, `standard` and `full` over thirteen tasks: MMLU, ARC Challenge, HellaSwag, TruthfulQA MC1, GSM8K, MGSM, IFEval, XSTest safe and unsafe, OR Bench hard and toxic, HumanEval, long context needle and output divergence. Every dataset is pinned to a commit.
* Deterministic, nested item sampling by hash; `--tasks`, `--limit` and offline `--data-dir`.
* Expected calibration error for every multiple choice task.
* Refusal detectors: keyword or any Hugging Face classifier (`--refusal-detector`), and `modeldiffr refusal-eval`.
* IFEval checks for 25 instruction types, without extra dependencies.
* HumanEval in a limited subprocess behind `--allow-code-execution`.
* Bootstrap p values, Benjamini Hochberg correction (`--fdr`), minimum effect sizes and a `negligible` verdict.
* A plan before every audit with the detectable change per task, `--plan-only`, `--estimate`, and `modeldiffr power`.
* Backends: batched transformers, vLLM, llama.cpp for GGUF, and OpenAI compatible APIs, chosen per model.
* GGUF fingerprints from quantized tensor bytes.
* `modeldiffr tasks`, and `verify --suite-data` to rebuild dataset suites.
* Colab notebook.
* Extras `tasks`, `vllm`, `llamacpp` and `all`.

**Changed**

* Report schema `0.3`: generic per task items, a `spec` on every metric, `plan`, and `verdict.negligible`. Manifest schema `modeldiffr.manifest/2`.
* Reports from 0.2 still verify.

## 0.2.0

*October 2026*

### Phase 1: trustworthy core

**Added**

* Weight fingerprints: SHA 256 per tensor and an RFC 6962 Merkle root that ignores how a checkpoint is sharded. Safetensors are read directly in every dtype; PyTorch checkpoints give the same root.
* `weights_diff` in every report: which tensors changed, were added or removed.
* Tokenizer, vocabulary and chat template fingerprints.
* Comparability checks before any model runs, recorded under `comparability`.
* One shared chat template for generation prompts when templates differ and tokenizers match, with the hash of every rendered prompt stored. Choose with `--template`.
* RFC 8785 canonical JSON and an `audit_id` computed from a manifest of models, suite and settings.
* `proof` section: suite root, results root and statement hash.
* `modeldiffr verify`, offline or against the real model files with `--models`.
* `modeldiffr fingerprint` for a single model.
* JSON Schema for reports, shipped in the package.
* Identical model control (50 seeded runs, zero changes), tamper tests, and a CPU integration test with a real transformers model in CI.
* Optional backend members `fingerprint`, `render_chat` and `generate_raw`.
* Exit codes `3` (pair not comparable) and `4` (verification failed).
* `proof` extra installing `jsonschema`.

**Changed**

* Report schema `0.2`. Reports from 0.1 cannot be verified.
* Docs moved from Mintlify to MkDocs Material, published on Netlify.

## 0.1.0

*2026*

### Phase 0 early preview

**Added**

* `modeldiffr audit` command comparing a base model with a derivative model.
* Built in `quick` suite: 24 capability items, 20 over refusal prompts, 12 neutral divergence texts.
* Metrics: capability accuracy (log likelihood scoring), over refusal rate, and token level KL divergence.
* Paired bootstrap confidence intervals. Changes are flagged only when the interval excludes zero.
* Self contained HTML report and versioned JSON report (schema 0.1).
* CI gate mode that exits with code 1 when any metric changes significantly.
* Python API through `run_audit`.
