# Modeldiffr Roadmap

This file is the public plan. It says what is shipped, what is next, and what is explicitly not claimed yet.

## Goal for v1.0

`pip install modeldiffr` audits any base and derivative pair across behavior, internal representations, and causal effect, on at least two major model families, with every report reproducible from its JSON.

## Phase 0: Foundation (current)

* [x] Public repository, Apache 2.0 license, contribution and security policies
* [x] Working behavioral smoke suite with confidence intervals
* [x] HTML and JSON reports
* [x] CI gate mode
* [x] Unit tests and CI on Python 3.10 to 3.12
* [x] PyPI release workflow

## Phase 1: Behavioral layer MVP

* [ ] Integrate standard benchmark subsets (MMLU, GSM8K, IFEval, XSTest) through an established evaluation harness
* [ ] Fast generation backend for larger models
* [ ] Chat template mismatch detection that fails loudly when prompts are not comparable
* [ ] Calibration metric (expected calibration error)
* [ ] Colab notebook that runs the quick suite on a free GPU
* [ ] Measured GPU hours per audit for the quick and full suites, recorded here

## Phase 2: First public audits

* [ ] Audit 3 to 4 public pairs: an official quantized build, a popular domain fine tune, a popular merge, and a positive control with a known regression
* [ ] Publish every report under `audits/`
* [ ] Write up the most significant finding, only when it is outside noise

## Phase 3: Representational and causal pilot

* [ ] Activation capture for both models on identical tokens
* [ ] Crosscoder training on a small model pair with a deliberately planted, harmless behavior
* [ ] Classify features as shared, base only, derivative only, or shifted
* [ ] Automatic plain language labels for the top shifted features, marked unverified
* [ ] Causal check: patching the top features should shrink the behavioral delta
* [ ] Measured cost curve to plan larger runs

## Phase 4 and beyond

* [ ] Representational and causal layers on Qwen, Llama, Gemma, and Mistral at 7B to 32B
* [ ] Public scale study of 20 to 30 popular derivative models
* [ ] Anomaly scan validated on test models with known planted behaviors, with its accuracy published either way
* [ ] v1.0 release and technical report

## Not claimed yet

* Modeldiffr does not yet detect backdoors or hidden behaviors. That claim will only be made after measured validation.
* The quick suite is a smoke test, not a benchmark.
