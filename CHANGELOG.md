# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## Unreleased

## 0.1.0 (2026)

### Added

* `modeldiffr audit` command comparing a base model with a derivative model.
* Built in `quick` suite: 24 capability items, 20 over refusal prompts, 12 neutral divergence texts.
* Metrics: capability accuracy (log likelihood scoring), over refusal rate, and token level KL divergence.
* Paired bootstrap confidence intervals; changes are flagged only when the interval excludes zero.
* Self contained HTML report and versioned JSON report (schema 0.1).
* CI gate mode that exits with code 1 when any metric changes significantly.
* Python API through `run_audit`.
