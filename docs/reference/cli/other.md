---
title: tasks, power, refusal-eval
description: Smaller commands for listing tasks, planning sample sizes and measuring refusal detectors.
---

# tasks, power, refusal-eval

Smaller commands for listing tasks, planning sample sizes and measuring refusal detectors.

## tasks

```bash
modeldiffr tasks
```

One line per task: kind, dataset with config, split and pinned commit, and the metrics it produces.

```text
mmlu            multiple_choice  cais/mmlu all test@c30699e835                     mmlu_accuracy, mmlu_ece
gsm8k           generation       openai/gsm8k main test@740312add8                 gsm8k_accuracy
```

## power

```bash
modeldiffr power --n 500 --rate 0.6
```

```text
with 500 paired items at a rate near 0.60, changes of about 6.1 points are detected 80% of the time
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--n` | required | Paired items |
| `--rate` | `0.5` | Expected accuracy or rate of the base model |
| `--power` | `0.8` | Chance of detecting a change of that size |
| `--alpha` | `0.05` | Two sided significance level |

The estimate assumes a correlation of 0.5 between the two models' per item results, which is conservative: closely related models correlate more, so real audits usually detect smaller changes. See [Statistics](../../concepts/statistics.md#power).

## refusal-eval

```bash
modeldiffr refusal-eval labeled.jsonl --detector hf:ProtectAI/distilroberta-base-rejection-v1
```

`labeled.jsonl` has one object per line with `response` (text) and `refused` (true or false), labeled by people.

```text
detector  hf:ProtectAI/distilroberta-base-rejection-v1
items     500
accuracy  0.9620
precision 0.9512
recall    0.9750
```

Use it to choose a detector before relying on refusal metrics, and quote the result next to the audit.
