---
title: Statistics
description: How Modeldiffr decides whether a change is real or just luck, in plain words.
---

# Statistics

How Modeldiffr decides whether a change is real or just luck.

## The problem

A score that goes from 79% to 75% on 24 questions means very little. Get one or two questions wrong by chance and you are there. So the real question is never "did the number move?". It is **"did it move more than luck would move it?"**

Modeldiffr answers that for every metric.

## Paired bootstrap

Used for every accuracy and rate.

Both models answer the same questions, so we can compare them question by question.

1. **Differences.** For each question, take `derivative score minus base score`. A question both got right gives 0. One only the derivative got right gives +1. One only the base got right gives minus 1.
2. **Resample.** Pick questions at random, with repeats allowed, until you have as many as the original set. Average their differences. Do this 2,000 times.
3. **Range.** Sort the 2,000 averages. The middle 95% (from the 2.5th to the 97.5th percentile) is the confidence range.
4. **Decide.** If the whole range is above zero or the whole range is below zero, the change is real.

**Why pairing matters.** Some questions are easy for every model, some are hard for every model. Comparing on the same question removes that, so the range is much tighter than comparing two separate averages. You need fewer questions to see a real change.

## One sample bootstrap

Used for `output_divergence_kl`. KL is already a comparison of the two models, so there is no "base value" to pair with. Modeldiffr resamples the per text KL values and calls it a real change only when:

```text
lower end of the range > 0.001
```

That small floor stops tiny floating point noise between identical models from counting as a change.

## P values

Every metric also gets a p value: roughly, how often luck alone would give a result at least this far from zero. It is computed from the same resamples.

## Testing many metrics at once

A `standard` audit reports about 25 metrics. If each has a 5% chance of a false alarm, one or two will look real by chance even between identical models.

Modeldiffr corrects for this with the Benjamini Hochberg method, which keeps the share of false alarms among the flagged metrics under 5%:

1. Sort the p values from smallest to largest.
2. Find the largest position `k` where `p value at k <= 0.05 × k / number of metrics`.
3. Metrics at positions 1 to `k` pass.

A metric is **significant** only when its range excludes zero **and** it passes this correction. Both results are stored. `significant_raw` is the range test alone. Change the target with `--fdr`.

## Too small to matter

A change can be real and still too small to care about. Each metric has a minimum size (`min_effect`): 1 point for accuracies, 2 points for refusal rates, 0.01 for calibration error. A real change below that is marked **negligible**. It is listed under `verdict.negligible`, not `verdict.changed`, so it does not fail a CI gate.

## Calibration error

Expected calibration error (ECE) measures whether a model's confidence matches how often it is right. It is not an average over questions, so it is resampled as a whole: each resample picks the same questions for both models, computes ECE for each, and takes the difference.

## How many questions do you need? { #power }

Before running, every task gets an estimate of the smallest change it can reliably detect (80% of the time, at a 5% error level):

```text
MDE = (z(0.975) + z(0.80)) x sqrt(2 p (1 - p) (1 - rho) / n)
```

`p` is the base score (0.5 if unknown), `rho = 0.5` is the assumed correlation between the two models, and `n` is the number of questions. With 500 questions that is about 6 points. With 1,000, about 4. So if you care about a 2 point drop, 200 questions is not enough. Use `modeldiffr power` to plan. The plan is also printed at the start of every audit.

## Repeatable

The bootstrap uses a seeded random generator. Same seed, same per question results, same range, every time.

```bash
modeldiffr audit base derivative --seed 0 --resamples 2000
```

## Fields in the report

| Field | Meaning |
| --- | --- |
| `n` | Number of paired questions |
| `base_mean` | Base average |
| `derivative_mean` | Derivative average |
| `delta` | Average difference |
| `ci_low`, `ci_high` | The 95% range |
| `confidence` | Range level, `0.95` |
| `p_value` | Bootstrap p value |
| `significant_raw` | The range excludes zero |
| `significant` | Also passes the many metrics correction |
| `negligible` | Real but smaller than `spec.min_effect` |
| `spec` | How the metric is computed: task, field, statistic, test, direction, `min_effect` |

!!! note

    A real change shows that something moved, not why. The [layer](layer_by_layer.md), [feature](representational.md) and [causal](causal.md) tools are there to answer why.