---
title: Representational layer
description: How Modeldiffr compares the insides of two models, from layer statistics to crosscoder features.
---

# Representational layer

How Modeldiffr compares the insides of two models, from layer statistics to crosscoder features.

The behavioral layer says *what* changed. This layer asks *where*: which layers moved, which directions changed, and which learned features are new, lost or reshaped. It needs both models loaded with transformers (`--backend hf`) and the same tokenizer; texts that tokenize differently are skipped and counted.

Three tools, from cheapest to most detailed:

| Command | Answers | Cost |
| --- | --- | --- |
| `modeldiffr layers` | Which layers changed, and by how much | One forward pass per model |
| `modeldiffr directions` | Did a known concept direction, such as refusal, move or weaken | Two small prompt sets |
| `modeldiffr features` | Which features are new, lost or shifted, with examples | Capture plus crosscoder training |

## Activations

For each text, both models run on exactly the same token ids, and the output of each chosen decoder layer (the residual stream after that block) is recorded at every position except the first. The first token is dropped because its activations are often orders of magnitude larger and would dominate every statistic. Activations are stored in float32 on the CPU.

## Layer statistics

For each layer, over the captured tokens:

| Statistic | Meaning | Identical models |
| --- | --- | --- |
| `cka` | Linear centered kernel alignment between the two activation matrices. Invariant to rotation and scale | 1 |
| `cosine` | Mean cosine similarity between paired token activations | 1 |
| `relative_change` | Mean of `|derivative - base| / |base|` per token | 0 |
| `mean_shift` | Distance between the two mean activations relative to the base mean's norm | 0 |
| `norm_ratio` | Mean activation norm of the derivative over the base | 1 |

A narrow fine tune usually leaves early layers close to identical and shows the first jump where its update has most effect. Start a crosscoder there.

## Directions

`directions` computes a difference of means direction at the last token of each prompt: the mean activation on prompts with a property minus the mean on prompts without it. This is the standard cheap probe for concepts such as refusal (Arditi et al., 2024).

For each layer it reports the cosine between the base's and the derivative's direction, and how far apart the two prompt sets sit along the *base's* direction in each model. An abliterated model typically keeps a similar direction (high cosine) but shows a much smaller separation along it.

## Crosscoders

A crosscoder learns one dictionary of sparse features that reconstructs both models' activations at once (Lindsey et al., 2024). Each feature has one encoder and one decoder vector per model. If a feature's derivative decoder has nearly all of its norm, the feature exists only in the derivative.

Modeldiffr trains a BatchTopK crosscoder (Bussmann et al., 2024), which keeps the `k × batch` largest activations across a batch instead of using an L1 penalty. This avoids the bias towards splitting features between models that L1 crosscoders show, a failure mode documented by Minder et al. (2025). At inference a single threshold, averaged from training, replaces the top k.

```text
encode   f = BatchTopK(relu(x_base W_base + x_deriv W_deriv + b))
decode   x̂_base = f D_base + c_base,   x̂_deriv = f D_deriv + c_deriv
loss     |x_base - x̂_base|² + |x_deriv - x̂_deriv|²
```

Each model's activations are scaled so their mean norm is √d before training, and the scales are stored with the weights.

### The delta variant

`--variant delta` ties the decoders: `D_deriv = D_shared + Δ`, with a group penalty that pushes most rows of `Δ` to zero. It suits narrow fine tunes, where most features should be untouched and only a few should carry the change.

### Classes

For feature `i`, with decoder vectors `b` (base) and `d` (derivative):

| Class | Rule |
| --- | --- |
| `dead` | Never active on the corpus |
| `base_only` | `|d| / (|b| + |d|) < 0.15` |
| `derivative_only` | `|d| / (|b| + |d|) > 0.85` |
| `shifted` | Otherwise, when `cos(b, d) < 0.5` |
| `shared` | Otherwise |

The histogram on the feature page shows the relative norm for every live feature. On identical models every feature sits in the middle; the tests check this.

### Examples and labels

For a few features in each class (`--per-class`), the page shows the contexts where the feature fires most strongly, with the token highlighted. With `--label-api` and `--label-model`, an OpenAI compatible model writes a short label from those examples. Labels are marked unverified everywhere, and the labeling prompt's hash is part of the manifest, so a changed prompt gives a different features id.

## Proof

`features.json` follows the same pattern as audit reports:

* a manifest of both model entries (with weight roots), the corpus (source, counts and a Merkle root over the texts), the layer, every crosscoder setting and the labeling setup;
* `id = mdrf1:` + SHA 256 of the manifest's canonical JSON;
* `result_sha256` over every field except itself;
* a `files` map with the SHA 256 of `crosscoder.safetensors`.

`modeldiffr verify features.json` checks all three. Training is deterministic for a given seed on the CPU; on a GPU, floating point order can make two runs differ slightly, so publish the weights file rather than relying on retraining.

With `--report report.json`, the features file records the audit id and the metrics that changed, and refuses to run if either model's weights differ from the audited ones.

## Limits

* A crosscoder sees one layer. Run `layers` first to choose it.
* Classes depend on thresholds. They are fixed and published, not tuned per model.
* Features found on a corpus are only those the corpus exercises. Use a corpus that resembles what the derivative was trained for, plus general text.
* Feature labels are hypotheses. Causal checks in the next layer test whether a feature actually drives a behavioral change.

## References

* Lindsey, J. et al. *Sparse Crosscoders for Cross Layer Features and Model Diffing.* Transformer Circuits Thread, Anthropic, 2024.
* Bussmann, B., Leask, P., Nanda, N. *BatchTopK Sparse Autoencoders.* 2024.
* Minder, J., Dumas, C. et al. *Overcoming Sparsity Artifacts in Crosscoders to Interpret Chat Tuning.* NeurIPS 2025 (arXiv 2504.02922).
* Arditi, A. et al. *Refusal in Language Models Is Mediated by a Single Direction.* 2024.
* Kornblith, S. et al. *Similarity of Neural Network Representations Revisited.* ICML 2019.
