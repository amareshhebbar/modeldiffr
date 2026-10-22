---
title: Technical report draft
description: The draft of the Modeldiffr technical report, with methods written and results to be filled from published audits.
---

# Technical report draft

The draft of the Modeldiffr technical report, with methods written and results to be filled from published audits. The LaTeX source is in [`paper/`](https://github.com/amareshhebbar/modeldiffr/tree/main/paper) and includes the tables written by `modeldiffr study`.

!!! note "Status"

    Methods and protocol are complete. Every result section is empty until the audits, the control study and the zoo are run and published, signed, in the public registry. No number will appear here that cannot be checked from a published report.

## Abstract

Open weight language models are routinely fine tuned, quantized, merged and edited, and the derivatives are shared with little evidence of what changed. We present Modeldiffr, an open source tool that audits a derivative against its base at four levels: behavior on standard benchmarks with paired, multiplicity corrected statistics; internal representations, through crosscoders that separate new, lost and shifted features; causal mediation, through layer and feature patching that measures how much of a behavioral change an internal change carries; and anomalous behavior on rare inputs, through a sweep and a gradient guided trigger search whose accuracy is measured on a zoo of models with planted triggers. Every result is bound to the exact weights by content addressed fingerprints and Merkle roots, and can be signed and timestamped, so a third party can check an audit without trusting its author. We report a study of *N* public derivatives across quantization, abliteration, instruction tuning and distillation.

## 1. Introduction

A derivative model inherits its base's reputation without inheriting its evaluation. Model cards rarely report what a fine tune or a quantization changed, and when they do, the comparison is often run on different prompts, templates or sample sizes than the base's published numbers. Three problems follow: changes inside noise are reported as findings, real regressions go unnoticed, and nobody can check either claim.

Modeldiffr treats the comparison itself as the object of study. Both models answer the same items under the same template; each change is reported with a paired interval and a correction across metrics; and the report commits to every item, result and setting so that it can be verified offline.

**Contributions.**

1. A verifiable audit format: canonical JSON manifests, weight fingerprints that ignore sharding, Merkle roots over items and results, and in toto attestations signed with Sigstore or a key.
2. A behavioral protocol with paired bootstrap intervals, Benjamini Hochberg correction, minimum effect sizes and power analysis before each run.
3. An integration of crosscoder model diffing and causal patching into the same audit, linked by ids and weight roots.
4. An anomaly scan released together with the model zoo used to measure its detection and false positive rates.
5. A study of public derivatives, with every audit signed and listed in a registry that verifies audits in the browser.

## 2. Related work

Evaluation harnesses such as the EleutherAI lm evaluation harness and UK AISI Inspect standardize tasks but compare models one at a time. Model diffing with crosscoders (Lindsey et al., 2024) and its refinements (Minder et al., 2025) compare internals without behavioral grounding. Causal mediation (Vig et al., 2020; Meng et al., 2022) and sparse feature circuits (Marks et al., 2024) explain behavior inside one model. Backdoor research (Hubinger et al., 2024; Rando and Tramèr, 2024) shows that hidden behaviors survive safety training; trigger search builds on adversarial suffix optimization (Zou et al., 2023). Supply chain work, including Sigstore, in toto and OpenSSF model signing, establishes provenance but not behavior.

## 3. The proof layer

See [Fingerprints and proof](concepts/proof.md) and [Attestations](concepts/attestation.md). Key definitions: weight root, audit id, results root, statement hash, predicate.

## 4. Behavioral layer

See [Metrics](concepts/metrics.md), [Statistics](concepts/statistics.md) and [Suites](concepts/suites.md). Paired bootstrap, two sided p values, Benjamini Hochberg at q = 0.05, minimum effects, the negligible verdict, and power.

## 5. Representational layer

See [Representational layer](concepts/representational.md). BatchTopK crosscoders, the delta variant, relative decoder norm and cosine classes with fixed thresholds.

## 6. Causal layer

See [Causal layer](concepts/causal.md). Share of the behavioral change reproduced by patching, with item resampled intervals, undefined when the change itself is not significant.

## 7. Anomaly scan

See [Anomaly scan](concepts/anomaly.md). Sweep, robust z scores, trigger search, random trigger reference, zoo construction with blind names.

## 8. Evaluation protocol

1. **Identical model control.** 50 seeded self audits; the expected number of changed metrics is zero.
2. **Planted regressions.** `examples/controls.yaml`; detection rate by perturbation size, false positives on identical copies.
3. **Zoo.** 20 backdoored and 20 clean models built from public small models; detection and false positive rates with Wilson intervals; AUCs.
4. **Public audits.** `examples/public_audits.yaml` and further pairs, all signed, all in the registry.

## 9. Results

*To be written from `study/study.md` and `study/study.tex`, the control study's `index.json`, and `zoo_eval.json`.*

## 10. Limitations

See [Limitations](limitations.md). A verified audit proves which models and items were compared and that the claims follow from the recorded results; it does not prove that the audit was run as recorded. Features and labels are hypotheses; causal shares are measured on multiple choice items only; zoo rates on small models do not transfer automatically to large models or to adaptive adversaries.

## 11. Responsible release

See [Responsible use](responsible_use.md). The zoo uses harmless triggers and targets. Modeldiffr ships no harmful prompts.
