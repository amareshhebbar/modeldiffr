---
title: Quickstart
description: Run your first audit in under five minutes.
---

# Quickstart

Run your first audit in under five minutes.

### 1. Install

```bash
pip install "modeldiffr[hf]"
```

### 2. Run an audit

Compare an instruct model with the base model it was made from:

```bash
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B --out reports/qwen_instruct_vs_base
```

Both arguments take a Hugging Face model id or a local folder. The first one is the base, the second is the derivative.

### 3. Read the terminal summary

```text
capability_accuracy      base 0.7917  derivative 0.7500  delta -0.0417  95% CI [-0.1667, +0.0833]  within noise
over_refusal_rate        base 0.1000  derivative 0.0000  delta -0.1000  95% CI [-0.2500, +0.0000]  within noise
output_divergence_kl     base 0.0000  derivative 0.4120  delta +0.4120  95% CI [+0.3051, +0.5233]  CHANGED

report: reports/qwen_instruct_vs_base/report.html
json:   reports/qwen_instruct_vs_base/report.json
```

!!! note

    These numbers only show the format. Run the command to get real values for your models.

How to read one line:

* `base` and `derivative` are the two scores.
* `delta` is derivative minus base.
* `95% CI` is the range the true difference most likely sits in.
* The last word is the verdict.

### 4. Open the report

The output directory contains two files:

| File | Purpose |
| --- | --- |
| `report.html` | Self contained page. Open it in any browser or attach it to a pull request. |
| `report.json` | Full machine readable result: every item, model revisions, settings, and wall time. |

## Reading the verdict

| Verdict | Meaning |
| --- | --- |
| `within noise` | The range includes zero. This could easily be luck. |
| `CHANGED` | The range does not include zero. The difference is bigger than luck would explain. |

The HTML report goes one step further and says **improved**, **regressed**, **changed** or **within noise**, based on whether higher or lower is better for that metric. See [Metrics](concepts/metrics.md). Why the range works: [Statistics](concepts/statistics.md).

## Progress output

Progress lines go to stderr, so stdout stays clean if you pipe it somewhere:

```text
[modeldiffr] loading base model Qwen/Qwen2.5-0.5B-Instruct
[modeldiffr] loading derivative model Qwen/Qwen2.5-0.5B
[modeldiffr] capability: scoring base
[modeldiffr] capability: scoring derivative
[modeldiffr] over refusal: generating with base
[modeldiffr] over refusal: generating with derivative
[modeldiffr] output divergence: computing KL on neutral text
```

## Run real benchmarks

The `quick` suite is only a smoke test. For a real decision, run the standard benchmarks:

```bash
pip install "modeldiffr[hf,tasks]"
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B --suite lite
```

See [Suites and tasks](concepts/suites.md), or [run it on a free Colab GPU](guides/colab.md).

## See where it changed

```bash
modeldiffr layers Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B
```

This prints one row per layer and the layer with the biggest change. See [Layer by layer comparison](concepts/layer_by_layer.md).

## Next steps

<div class="grid cards" markdown>

-   **[CLI reference](reference/cli/audit.md)**

    ---

    Every flag on `modeldiffr audit`.

-   **[Python API](guides/python_usage.md)**

    ---

    Run audits from your own code.

</div>