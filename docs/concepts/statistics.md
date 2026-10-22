---
title: Statistics
description: Why every number carries a confidence interval, and how it is computed.
---

# Statistics

Why every number carries a confidence interval, and how it is computed.

A score moving from 0.79 to 0.75 on 24 items says very little on its own. Modeldiffr answers the real question: **is this difference larger than what evaluation noise would produce?**

## Paired bootstrap

Used for every accuracy and rate. Both models answer the same items, so the analysis works on per item differences.

### 1. Compute differences

For each item `i`, compute `d_i = derivative_i - base_i`.

### 2. Resample

Draw `n` differences with replacement and take their mean. Repeat `n_resamples` times (default 2000).

### 3. Take percentiles

Sort the resampled means. The 95% interval is the 2.5th and 97.5th percentile.

### 4. Decide

The change is **significant** when `ci_low > 0` or `ci_high < 0`.

Pairing matters. Item difficulty varies a lot, and pairing removes that variance from the comparison, which gives tighter intervals than comparing two independent means.

## One sample bootstrap

Used for `output_divergence_kl`. There is no base value to pair with, because KL is already a comparison. Modeldiffr bootstraps the per text KL values against zero and marks the change significant only when

```text
ci_low > min_effect
```

with `min_effect = 1e-3`. This keeps floating point noise between identical checkpoints from being reported.

## P values

Every metric also carries a two sided bootstrap p value: twice the share of resampled differences on the far side of zero, capped at 1. For one sample metrics it is the share of resampled means at or below `min_effect`.

## Many metrics at once

A `standard` audit reports about 25 metrics. At a 5% error rate each, one or two would look significant by chance even between identical models. Modeldiffr controls the false discovery rate across all metrics in an audit with the Benjamini Hochberg procedure:

1. Sort the m p values from smallest to largest.
2. Find the largest rank k with `p_(k) <= q * k / m`, where `q` is the target rate (`--fdr`, default `0.05`).
3. Metrics with rank up to k pass.

A metric is **significant** only when its interval excludes zero **and** it passes the correction. Both are stored: `significant_raw` is the interval test alone.

## Negligible changes

A change can be real and still too small to matter. Each metric has a `min_effect`, 1 point for accuracies, 2 points for refusal rates, 0.01 for calibration error. A significant change smaller than that is marked **negligible** and listed under `verdict.negligible` instead of `verdict.changed`, so it does not fail a CI gate.

## Calibration error

Expected calibration error is not an average over items, so it is bootstrapped as a statistic: each resample draws the same item indices for both models, computes ECE for each, and takes the difference.

## Power

Before running, each task gets the smallest change it can detect 80% of the time at a 5% level, for a paired binary metric:

```text
MDE = (z(0.975) + z(0.80)) x sqrt(2 p (1 - p) (1 - rho) / n)
```

with `p` the base rate (0.5 when unknown) and `rho = 0.5` the assumed correlation between the two models' results. With 500 items that is about 6 points; with 1,000 about 4. Use `modeldiffr power` to plan, and see the plan printed at the start of every audit.

## Reproducibility

The bootstrap uses Python's `random.Random(seed)`. The same seed and the same per item results always produce the same interval.

```bash
modeldiffr audit base derivative --seed 0 --resamples 2000
```

## Fields produced

Every metric in `report.json` carries:

| Field | Description |
| --- | --- |
| `n` | Number of paired items |
| `base_mean` | Mean over base items |
| `derivative_mean` | Mean over derivative items |
| `delta` | Mean of differences |
| `ci_low`, `ci_high` | Interval bounds |
| `confidence` | Interval level, `0.95` |
| `p_value` | Two sided bootstrap p value |
| `significant_raw` | The interval excludes zero |
| `significant` | Also passes the false discovery rate correction |
| `negligible` | Significant but smaller than `spec.min_effect` |
| `spec` | How the metric is computed: task, field, statistic, test, direction, `min_effect` |

!!! note

    A significant result is evidence that something moved, not an explanation of why. The representational and causal layers on the [roadmap](../roadmap.md) exist to answer the why.
