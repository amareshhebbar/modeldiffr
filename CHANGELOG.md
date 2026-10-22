# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## Unreleased

## 0.9.0 (October 2026)

Phase 8: toward v1.0.

### Added

* `modeldiffr study`: tables by derivative kind and by metric from a folder of audits, as `study.md`, `study.csv`, `study.tex` and `study.json`. Batch specs accept `kind`.
* JSON Schemas for `features.json`, `causal.json`, `scan.json` and the attestation predicate; `verify` validates artifacts against them.
* Report schema 0.3 is the 1.0 candidate; the compatibility promise is documented.
* `GOVERNANCE.md`, `MAINTAINERS.md`, `RELEASING.md`, and a technical report draft in `paper/`.

### Changed

* Documentation redesigned: new home page, typography, color system, dark mode and page layouts. Report, feature, causal and scan pages share one visual system.

## 0.8.0 (October 2026)

Phase 7: anomaly scan.

### Added

* `modeldiffr scan`: a seeded rare input sweep scored by per token KL divergence with robust z scores, and a gradient guided trigger search compared with random triggers; `scan.json` and `scan.html`.
* `modeldiffr zoo make` and `modeldiffr zoo eval`: fine tuned clean and backdoored copies of a model with harmless triggers, blind names and a separate answer key; detection and false positive rates with Wilson intervals, AUCs and trigger recovery.
* `modeldiffr verify` checks scan files; the registry shows scan results.

## 0.7.0 (October 2026)

Phase 6: causal layer.

### Added

* `modeldiffr causal`: layer patching in both directions, crosscoder feature patching for the top attributed features and for all new, lost and shifted features, and steering along the mean difference, each with the share of the behavioral change reproduced and a bootstrap interval.
* `causal.json` and `causal.html`; `modeldiffr verify` checks them; the registry shows the share on the audit page.

### Changed

* Features files record the crosscoder weight hash under `files`, shared with causal files.

## 0.6.0 (October 2026)

Phase 5: representational layer.

### Added

* `modeldiffr layers`: linear CKA, cosine, relative change, mean shift and norm ratio for every layer.
* `modeldiffr directions`: difference of means directions compared between the models.
* `modeldiffr features`: BatchTopK crosscoders (standard and delta), feature classes, top contexts, optional unverified labels, `features.json`, `features.html` and `crosscoder.safetensors`.
* `modeldiffr verify` checks features files.
* Registry pages show feature counts when `features.json` sits next to the report.

## 0.5.0 (October 2026)

Phase 4: public audits, tooling.

### Added

* `modeldiffr controls make`: identity, noise, scale, zero and pruning controls written from safetensors shards, seeded and recorded in `modeldiffr_control.json`.
* `modeldiffr batch`: many audits from YAML or JSON, resume, `--only`, `--dry-run`, controls made on the fly, scored detection and false positive rates in `index.json`.
* `modeldiffr registry build`: a static site that lists verified audits and recomputes audit ids, Merkle roots, statement hashes and Ed25519 signatures in the browser.
* `examples/public_audits.yaml` and `examples/controls.yaml`.
* Extra `batch`.

## 0.4.0 (October 2026)

Phase 3: proof, signing and integrations.

### Added

* in toto Statement v1 for every report, predicate type `https://modeldiffr.dev/attestation/audit/v1`.
* `modeldiffr keygen` and `modeldiffr sign` with Ed25519 keys (`report.dsse.json`) or Sigstore keyless signing (`report.sigstore.json`); `audit --sign-key` and `audit --sigstore`.
* `verify --key`, `--identity`, `--issuer`, `--staging` and `--rpc`; signatures are bound to the report's audit id, results root, statement hash and verdict.
* OpenSSF model signing check for `model.sig` in audited models.
* `modeldiffr anchor ots`, `anchor upgrade` and `anchor eas` for OpenTimestamps and the Ethereum Attestation Service.
* `modeldiffr commit` and `modeldiffr reveal` for private holdout suites.
* `modeldiffr bom` for CycloneDX 1.6 and SPDX 3.0.1.
* `modeldiffr hub push`, `modeldiffr badge`, and Hub URLs as model references.
* GitHub Action (`action.yml`) that audits, gates, signs and uploads.
* Extras `sign` and `anchor`.

## 0.3.0 (October 2026)

Phase 2: behavioral layer.

### Added

* Suites `lite`, `standard` and `full` over thirteen tasks with pinned datasets: MMLU, ARC Challenge, HellaSwag, TruthfulQA MC1, GSM8K, MGSM, IFEval, XSTest safe and unsafe, OR Bench hard and toxic, HumanEval, long context needle, output divergence.
* Deterministic nested sampling, `--tasks`, `--limit`, offline `--data-dir`.
* Calibration error, harmful compliance, IFEval (25 instruction types), HumanEval behind `--allow-code-execution`.
* Refusal detectors (`--refusal-detector`) and `modeldiffr refusal-eval`.
* P values, Benjamini Hochberg correction (`--fdr`), minimum effects and a `negligible` verdict.
* Plan with detectable change per task, `--plan-only`, `--estimate`, `modeldiffr power`.
* Backends: batched transformers, vLLM, llama.cpp with GGUF fingerprints, OpenAI compatible APIs, per model.
* `modeldiffr tasks`, `verify --suite-data`, Colab notebook, extras `tasks`, `vllm`, `llamacpp`, `all`.

### Changed

* Report schema 0.3 and manifest schema 2. Reports from 0.2 still verify.

## 0.2.0 (October 2026)

Phase 1: trustworthy core.

### Added

* Weight fingerprints: SHA 256 per tensor and an RFC 6962 Merkle root that ignores sharding; safetensors read directly in every dtype, PyTorch checkpoints give the same root.
* `weights_diff` in every report: which tensors changed, were added or removed.
* Tokenizer, vocabulary and chat template fingerprints.
* Comparability checks recorded under `comparability`, and one shared chat template for generation prompts when templates differ (`--template`), with the hash of every rendered prompt.
* RFC 8785 canonical JSON and an `audit_id` computed from a manifest of models, suite and settings.
* `proof` section with suite root, results root and statement hash.
* `modeldiffr verify` (offline, or `--models` against the real files) and `modeldiffr fingerprint`.
* JSON Schema for reports shipped in the package; `proof` extra.
* Identical model control, tamper tests and a CPU integration test with a real transformers model in CI.
* Exit codes 3 (pair not comparable) and 4 (verification failed).

### Changed

* Report schema 0.2.
* Docs moved from Mintlify to MkDocs Material on Netlify.

## 0.1.0 (2026)

### Added

* `modeldiffr audit` command comparing a base model with a derivative model.
* Built in `quick` suite: 24 capability items, 20 over refusal prompts, 12 neutral divergence texts.
* Metrics: capability accuracy (log likelihood scoring), over refusal rate, and token level KL divergence.
* Paired bootstrap confidence intervals; changes are flagged only when the interval excludes zero.
* Self contained HTML report and versioned JSON report (schema 0.1).
* CI gate mode that exits with code 1 when any metric changes significantly.
* Python API through `run_audit`.
