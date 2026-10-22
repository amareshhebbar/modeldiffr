# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## Unreleased

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
