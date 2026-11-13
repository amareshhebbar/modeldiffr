---
title: Causal tests
description: How Modeldiffr tests whether a layer, a set of features or one direction actually causes a behavior change.
---

# Causal tests

How Modeldiffr tests whether a layer, a set of features or one direction actually **causes** a behavior change.

## Why this step exists

Finding a new feature does not prove it matters. It might be new and harmless. The only way to know is to try it: take the base model, swap in the derivative's version of that part, and see whether the base starts behaving like the derivative.

That is what `modeldiffr causal` does. It is like replacing one part in a machine with the part from a second machine, and checking whether the first machine now behaves like the second.

## The measurement

The test uses multiple choice questions, because you can read the effect directly without sampling text. For every question, Modeldiffr records the probability the model gives to the correct answer:

* `b` for the base,
* `d` for the derivative,
* `c` for the base with one part swapped in.

Then:

```text
share = mean(c - b) / mean(d - b)
```

In words: of the total difference between base and derivative, how much did the swap reproduce?

| Share | Meaning |
| --- | --- |
| 100% | The swap turns the base fully into the derivative on these questions |
| 0% | The swap does nothing |
| Above 100% | The swap overshoots |
| Below 0% | The swap pushes the other way |

Questions are resampled to give a 95% range for both the behavior change and the share. If the behavior change itself is not real (its range includes zero), there is nothing to explain, and the share is reported as not available instead of a noisy ratio.

## The swaps

Every swap acts on the output of one layer, for every token.

| Name | What is swapped | Question it answers |
| --- | --- | --- |
| `patch_layer` | Base layer output replaced by the derivative's | Is the whole change already decided at this layer? |
| `reverse_layer` | Derivative layer output replaced by the base's | Does the change need this layer? |
| `patch_top_N` | Only the N features that differ the most | Do a few features carry it? |
| `patch_changed_classes` | Every new, lost and shifted feature | Do the features the crosscoder flagged carry it? |
| `steer_A` | Base output plus `A` times the average difference between the two models | Is the whole change one simple direction? |

For a feature set `S`, the patched output is:

```text
h' = h_base + sum over i in S of f_i (D_deriv,i - D_base,i)
```

where `f_i` is how strongly feature `i` fires and `D` are the crosscoder decoders. Patching every feature gives the full layer patch, minus the crosscoder's reconstruction error. So `patch_top_N / patch_layer` is the share of the layer's effect that those N features explain.

Features are ranked by attribution: the average over task tokens of `f_i × |D_deriv,i - D_base,i|`, which is how much each feature moves the output between the two models.

## How to read the results

* `patch_layer` near 100% at a middle layer: everything that matters for these questions is decided by that layer. Run it at a few layers to find where the change becomes complete.
* Small `patch_top_50` but large `patch_layer`: the change is spread over many features, or sits in what the crosscoder could not rebuild.
* Large `steer_1`: the change is close to a single direction. Abliteration does this by design.

## Proof

`causal.json` has a manifest with both models, the layer, the exact questions (with a Merkle root), the crosscoder weight hash and features id if used, and every setting. Its id is `mdrc1:` plus the manifest hash. `modeldiffr verify causal.json` checks the id and the result hash. With `--report`, it is linked to an audit and refuses models whose weights differ from the audited ones.

## Limits

* Multiple choice questions only. Generation tasks need sampled outputs and a judge, which is much more expensive. On the roadmap.
* One layer per run. A change that needs several layers together shows up as partial shares at each.
* Runs one sequence at a time on the transformers backend, so keep `--limit` modest on large models.

## References

* Vig, J. et al. *Investigating Gender Bias in Language Models Using Causal Mediation Analysis.* NeurIPS 2020.
* Meng, K. et al. *Locating and Editing Factual Associations in GPT.* NeurIPS 2022.
* Turner, A. et al. *Steering Language Models With Activation Engineering.* 2023.
* Marks, S. et al. *Sparse Feature Circuits.* 2024.