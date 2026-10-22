---
title: Changelog
description: Release history. The project uses Semantic Versioning.
---

# Changelog

Release history. The project uses Semantic Versioning.

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
