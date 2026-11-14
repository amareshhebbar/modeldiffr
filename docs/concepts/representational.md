---
title: Features
description: How Modeldiffr finds internal features that are new, lost or reshaped in the derivative, using crosscoders.
---

# Features

How Modeldiffr finds the internal features that are new, lost or reshaped in the derivative.

[Layer by layer comparison](layer_by_layer.md) tells you **which layer** changed. This page is about the next question: **what** changed at that layer.

## What is a feature?

Inside a layer, the model stores many ideas at once in one long vector. Single numbers in that vector rarely mean anything on their own. But certain **directions** in that vector do: one direction might light up for "Python code", another for "the user is asking something unsafe".

A feature is one of those meaningful directions. If we can list the features of both models, we can see which ones the fine tune added, removed or changed.

## What is a crosscoder?

A crosscoder is a small model that we train to learn those features. It looks at the same layer in **both** models at the same time and learns one shared list of features that explains both.

For each feature it learns two things per model:

* how to detect the feature from that model's layer output (the encoder),
* how much of that model's output the feature writes back (the decoder).

The trick: if a feature has a strong decoder in the derivative and almost nothing in the base, that feature only exists in the derivative. If it is strong in both, it is shared.

This approach comes from Anthropic's crosscoder work (Lindsey et al., 2024).

## How it works, step by step

1. **Capture.** Both models read the same tokens. The output of the chosen layer is saved for every token, in both models. This is the same capture used by `modeldiffr layers`.
2. **Scale.** Each model's activations are scaled so they have the same average size. Otherwise the bigger model would dominate training.
3. **Train.** The crosscoder learns to rebuild both models' activations from a small number of active features per token. Modeldiffr uses the **BatchTopK** method: in each batch, only the strongest `k` features per token on average are kept on, and the rest are set to zero.
4. **Classify.** For every feature, compare its decoder strength in the two models and sort it into a class.
5. **Show examples.** For a sample of features in each class, find the text where the feature fires the strongest and show it with the token highlighted.
6. **Save and lock.** Write `features.json`, `features.html` and the crosscoder weights, with hashes so anyone can verify them.

```text
encode   f = BatchTopK(relu(x_base W_base + x_deriv W_deriv + b))
decode   x̂_base = f D_base + c_base,   x̂_deriv = f D_deriv + c_deriv
loss     |x_base - x̂_base|² + |x_deriv - x̂_deriv|²
```

### Why BatchTopK

Older crosscoders used an L1 penalty to keep features sparse. Research (Minder et al., 2025) showed that L1 tends to split one real feature into a "base" copy and a "derivative" copy, making shared features look new. BatchTopK does not have that bias as strongly, so the "new" and "lost" lists are more trustworthy.

### The delta variant

`--variant delta` is for narrow fine tunes. It forces the derivative decoder to be the base decoder plus a small difference, and penalizes that difference. Most features then stay exactly shared, and only the few that really changed carry a difference. This matches what a narrow fine tune actually does.

## The classes

For feature `i`, let `b` be its base decoder vector and `d` its derivative decoder vector.

| Class | Rule | Plain meaning |
| --- | --- | --- |
| `dead` | Never fires on the corpus | Not used on this text |
| `base_only` | `|d| / (|b| + |d|) < 0.15` | The base has it, the derivative lost it |
| `derivative_only` | `|d| / (|b| + |d|) > 0.85` | New in the derivative |
| `shifted` | Neither of the above, and `cos(b, d) < 0.5` | Both have it, but it now writes something different |
| `shared` | Everything else | Unchanged |

These thresholds are fixed and published. They are never tuned per model, so results stay comparable across audits. On two identical models, every live feature lands in the middle as `shared`, and the tests check this.

## Labels

With `--label-api` and `--label-model`, a language model reads each feature's top examples and writes a short label like "dates in legal text". Labels are always marked **unverified**. They are guesses. The prompt used for labeling is hashed into the file, so a changed labeling prompt gives a different features id.

## Why this is needed

* Layer statistics say "layer 14 moved by 15%". That is a location, not an explanation.
* Benchmarks say "refusals dropped 30%". That is a symptom, not a mechanism.
* Features connect the two: "at layer 14, these 41 features are new, and they fire on requests that look unsafe". That is something a person can read, check and act on.

## Proof

`features.json` works like an audit report:

* a manifest with both models (including weight hashes), the corpus (with a Merkle root over the texts), the layer, every crosscoder setting and the labeling setup,
* an id: `mdrf1:` plus the SHA 256 of the manifest,
* a hash over the results,
* a hash of `crosscoder.safetensors`.

`modeldiffr verify features.json` checks all of it. With `--report report.json`, the file is linked to an audit and refuses to run if either model's weights differ from the audited ones.

Training is deterministic for a given seed on CPU. On GPU, tiny floating point differences can make two runs differ slightly, so publish the weights file instead of asking people to retrain.

## Limits

* One layer per crosscoder. Run [`layers`](layer_by_layer.md) first to choose it.
* Only features the corpus actually triggers can be found. Use text close to what the derivative was trained for, plus general text.
* Features close to a class threshold could fall either way.
* Labels are hypotheses. The [causal layer](causal.md) tests whether a feature actually drives a behavior change.

## References

* Lindsey, J. et al. *Sparse Crosscoders for Cross Layer Features and Model Diffing.* Transformer Circuits Thread, Anthropic, 2024.
* Bussmann, B., Leask, P., Nanda, N. *BatchTopK Sparse Autoencoders.* 2024.
* Minder, J., Dumas, C. et al. *Overcoming Sparsity Artifacts in Crosscoders to Interpret Chat Tuning.* NeurIPS 2025 (arXiv 2504.02922).
* Kornblith, S. et al. *Similarity of Neural Network Representations Revisited.* ICML 2019.