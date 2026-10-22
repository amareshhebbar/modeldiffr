---
title: Causal layer
description: Interventions that measure how much of a behavioral change runs through one layer, a set of crosscoder features, or one direction.
---

# Causal layer

Interventions that measure how much of a behavioral change runs through one layer, a set of crosscoder features, or one direction.

Finding a new feature does not show that it matters. The causal layer changes the base model's computation in a controlled way and measures how much of the derivative's behavior appears. If the derivative answers some questions differently, and putting the derivative's version of 50 features into the base makes the base answer them the same way, those features carry the change.

## The measurement

`modeldiffr causal` works on multiple choice items, where the effect of an intervention can be read without sampling. For every item it computes the probability the model gives to the correct option, normalized over the options. Call the per item values `b` (base), `d` (derivative) and `c` (base under an intervention). Then

```text
share = mean(c - b) / mean(d - b)
```

A share of 100% means the intervention moves the base all the way to the derivative on these items; 0% means it does nothing. Values outside that range are possible and meaningful: overshoot, or a change in the opposite direction.

Items are resampled with replacement to give a 95% interval for both the behavioral change `mean(d - b)` and the share. If the interval for the behavioral change includes zero, there is nothing to explain, and the share is reported as not available rather than as a noisy ratio.

## Interventions

All interventions act on the output of one decoder layer, at every position, for the exact token ids being scored.

| Name | What is changed | Question it answers |
| --- | --- | --- |
| `patch_layer` | Base layer output replaced by the derivative's | Is the change fully set by this point in the network? |
| `reverse_layer` | Derivative layer output replaced by the base's; the share measures how much of the change is removed | Does the change need this layer's state? |
| `patch_top_N` | Base output plus the derivative's minus the base's contribution of the N features with the largest attribution | Do a few features carry it? |
| `patch_changed_classes` | The same for every new, lost and shifted feature | Do the features the crosscoder flagged carry it? |
| `steer_A` | Base output plus `A` times the mean difference between the two models' outputs on the task tokens | Is the change one direction? |

For a feature set `S`, with crosscoder activations `f` computed from both models' activations on the same token and decoders `D` divided by each model's input scale:

```text
h' = h_base + Σ_{i ∈ S} f_i (D_deriv,i − D_base,i)
```

Patching every feature reproduces the full layer patch up to the crosscoder's reconstruction error, so `patch_top_N / patch_layer` is the share of the layer's effect those features account for.

Feature attribution is the mean over task tokens of `f_i × |D_deriv,i − D_base,i|`: how much each feature moves the activation between the two models on these items.

## Reading the results

* `patch_layer` near 100% at a middle layer says everything that matters for these items is decided by that layer. Run the check at several layers to find where the change becomes complete.
* A small `patch_top_50` with a large `patch_layer` says the change is spread over many features, or lives in the crosscoder's error term.
* A large `steer_1` says the change is close to a single direction, as abliteration produces by design.

## Proof

`causal.json` has a manifest of both model entries, the layer, the suite name with a Merkle root over the exact items, the crosscoder weight hash and features id when one was used, and every setting. Its id is `mdrc1:` plus the hash of the manifest, and `modeldiffr verify causal.json` checks the id and the result hash. With `--report`, it records the audit id and refuses models whose weights differ from the audited ones.

## Limits

* Multiple choice items only. Generation tasks need sampled outputs and a judge, which makes interventions far more expensive; this is on the roadmap.
* One layer per run. A change that depends on several layers together shows up as partial shares at each.
* Interventions are run one sequence at a time on the transformers backend, so keep `--limit` modest on large models.

## References

* Vig, J. et al. *Investigating Gender Bias in Language Models Using Causal Mediation Analysis.* NeurIPS 2020.
* Meng, K. et al. *Locating and Editing Factual Associations in GPT.* NeurIPS 2022.
* Turner, A. et al. *Steering Language Models With Activation Engineering.* 2023.
* Marks, S. et al. *Sparse Feature Circuits.* 2024.
