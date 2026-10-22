---
title: modeldiffr audit
description: Compare a base model with a derivative model.
---

# modeldiffr audit

Compare a base model with a derivative model.

```bash
modeldiffr audit BASE DERIVATIVE [options]
```

## Arguments

#### `base`

*string*, required

Base model. A Hugging Face model id such as `Qwen/Qwen2.5-0.5B-Instruct`, or a local path.

#### `derivative`

*string*, required

Derivative model: a fine tune, quantized build, merge, or edited checkpoint. Model id or local path.

## Options

#### `--suite`

*string*, default `quick`

Evaluation suite. Must be a registered suite name. Run `modeldiffr suites` to list them.

#### `--out`

*string*, default `modeldiffr_report`

Output directory for `report.json` and `report.html`. Created if missing. Existing reports are overwritten.

#### `--device`

*string*, default `auto`

`auto`, `cpu`, `cuda`, `cuda:0`, or `mps`. `auto` picks CUDA, then MPS, then CPU. Both models load on the same device.

#### `--dtype`

*string*, default `auto`

`auto`, `float32`, `float16`, or `bfloat16`. Applied to both models. `auto` follows each checkpoint's config.

#### `--base-revision`

*string*

Pin the base model to a branch, tag, or commit hash.

#### `--derivative-revision`

*string*

Pin the derivative model to a branch, tag, or commit hash.

#### `--seed`

*integer*, default `0`

Seed for the bootstrap.

#### `--resamples`

*integer*, default `2000`

Number of bootstrap resamples. More resamples give more stable interval bounds at a small CPU cost.

#### `--trust-remote-code`

*flag*

Allow custom model code from the Hub. Applied to both models. Only enable for repositories you trust.

#### `--fail-on-change`

*flag*

CI gate mode. Exit with code `1` when any metric changes significantly.

#### `--template`

*string*, default `auto`

`auto`, `base`, `derivative` or `own`. Which chat template renders generation prompts. `auto` keeps each model's own template when they match, and uses one shared template when they differ but the tokenizers match, so both models receive identical text. `own` always uses each model's own template. See [comparable prompts](../../concepts/proof.md#comparable-prompts).

#### `--no-weight-hash`

*flag*

Skip hashing the weight files. Faster for very large models, but the report is no longer tied to exact weights and has no tensor level diff.

## Output

```text
audit id mdr1:71e153dc730bb9ec20b7159dc8845afab76de27ddf94b99cada26c713aa3170d
weights: 1 of 21 shared tensors changed, 0 added, 0 removed

capability_accuracy      base 0.7917  derivative 0.7500  delta -0.0417  95% CI [-0.1667, +0.0833]  within noise
over_refusal_rate        base 0.1000  derivative 0.0000  delta -0.1000  95% CI [-0.2500, +0.0000]  within noise
output_divergence_kl     base 0.0000  derivative 0.4120  delta +0.4120  95% CI [+0.3051, +0.5233]  CHANGED

report: audit/report.html
json:   audit/report.json
```

Warnings from the comparability check are printed above the metrics. Check the report afterwards with [`modeldiffr verify`](verify.md).

## Examples

=== "Basic"

    ```bash
    modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct your-org/your-qwen-finetune
    ```

=== "Pinned"

    ```bash
    modeldiffr audit org/base org/derivative \
      --base-revision BASE_COMMIT_SHA \
      --derivative-revision DERIVATIVE_COMMIT_SHA \
      --dtype bfloat16 \
      --seed 0 \
      --out audits/derivative_v2
    ```

=== "Local checkpoint"

    ```bash
    modeldiffr audit org/base ./checkpoints/step_4000 --device cuda:0
    ```

=== "CI gate"

    ```bash
    modeldiffr audit org/base ./checkpoints/candidate --fail-on-change --out audit
    ```

## Output

```text
capability_accuracy      base 0.7917  derivative 0.7500  delta -0.0417  95% CI [-0.1667, +0.0833]  within noise
over_refusal_rate        base 0.1000  derivative 0.0000  delta -0.1000  95% CI [-0.2500, +0.0000]  within noise
output_divergence_kl     base 0.0000  derivative 0.4120  delta +0.4120  95% CI [+0.3051, +0.5233]  CHANGED

report: modeldiffr_report/report.html
json:   modeldiffr_report/report.json
```

When a metric is skipped, a line such as `note: Skipped output divergence: the two models use different tokenizers.` is printed before the paths.
