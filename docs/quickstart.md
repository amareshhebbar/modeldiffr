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

Compare an instruct model with its base model:
```bash
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B --out reports/qwen_instruct_vs_base
```
Both arguments accept a Hugging Face model id or a local path.

### 3. Read the terminal summary

```text
capability_accuracy      base 0.7917  derivative 0.7500  delta -0.0417  95% CI [-0.1667, +0.0833]  within noise
over_refusal_rate        base 0.1000  derivative 0.0000  delta -0.1000  95% CI [-0.2500, +0.0000]  within noise
output_divergence_kl     base 0.0000  derivative 0.4120  delta +0.4120  95% CI [+0.3051, +0.5233]  CHANGED

report: reports/qwen_instruct_vs_base/report.html
json:   reports/qwen_instruct_vs_base/report.json
```

!!! note

    These numbers illustrate the format only. Run the command to get real values for your models.

### 4. Open the report

The output directory contains two files:

| File | Purpose |
| --- | --- |
| `report.html` | Self contained page. Open it in any browser or attach it to a pull request. |
| `report.json` | Full machine readable result: every item, model revisions, settings, and wall time. |

## Reading the verdict

Each metric line ends with one of two flags.

| Flag | Meaning |
| --- | --- |
| `within noise` | The 95% interval includes zero. No evidence of a real change. |
| `CHANGED` | The interval excludes zero. The difference is larger than evaluation noise. |

The HTML report goes one step further and labels each metric as **improved**, **regressed**, **changed**, or **within noise**, using the metric's direction. See [Metrics](concepts/metrics.md).

## Progress output

Progress lines go to stderr, so stdout stays clean for piping:

```text
[modeldiffr] loading base model Qwen/Qwen2.5-0.5B-Instruct
[modeldiffr] loading derivative model Qwen/Qwen2.5-0.5B
[modeldiffr] capability: scoring base
[modeldiffr] capability: scoring derivative
[modeldiffr] over refusal: generating with base
[modeldiffr] over refusal: generating with derivative
[modeldiffr] output divergence: computing KL on neutral text
```

## Next steps

<div class="grid cards" markdown>

-   **[CLI reference](reference/cli/audit.md)**

    ---

    Every flag on `modeldiffr audit`.

-   **[Python API](guides/python_usage.md)**

    ---

    Run audits from your own code.

</div>
