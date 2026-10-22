---
title: Batch audits
description: Run many audits from one YAML or JSON file, resume after interruptions, and score planted changes.
---

# Batch audits

Run many audits from one YAML or JSON file, resume after interruptions, and score planted changes.

```bash
pip install "modeldiffr[hf,tasks,batch]"
modeldiffr batch audits.yaml
```

## The spec

```yaml audits.yaml
out: audits
defaults:
  suite: lite
  dtype: bfloat16
  sign:
    key: keys/acme.key
audits:
  - name: qwen-q4
    base: Qwen/Qwen2.5-1.5B-Instruct
    derivative: Qwen/Qwen2.5-1.5B-Instruct-GGUF:qwen2.5-1.5b-instruct-q4_k_m.gguf
    base_backend: hf
  - name: our-finetune
    base: Qwen/Qwen2.5-1.5B-Instruct
    derivative: ./checkpoints/v7
    tasks: gsm8k,ifeval,xstest_safe
    expect: no_change
  - name: noise-control
    base: Qwen/Qwen2.5-1.5B-Instruct
    control: {kind: noise, strength: 0.2}
```

Every key in `defaults` applies to every audit unless the audit sets it. `args` lists are joined, defaults first.

| Key | CLI option |
| --- | --- |
| `suite`, `tasks`, `limit`, `seed`, `resamples`, `fdr` | same names |
| `backend`, `base_backend`, `derivative_backend` | `--backend`, `--base-backend`, `--derivative-backend` |
| `base_revision`, `derivative_revision`, `dtype`, `device`, `template` | same names |
| `data_dir`, `refusal_detector` | `--data-dir`, `--refusal-detector` |
| `allow_code_execution`, `trust_remote_code`, `no_weight_hash` | flags, set to `true` |
| `sign.key`, `sign.sigstore` | `--sign-key`, `--sigstore` |
| `args` | appended as is |

`name` must be unique and made of letters, digits, dots, dashes and underscores; it becomes the report folder. `kind` is a free label such as `quantization` or `abliterated` that [study tables](study.md) group by. `expect` is `change` or `no_change` and turns the audit into a scored control. A `control` entry makes a perturbed copy under `OUT/_controls/NAME` first and sets `expect` from its kind.

## Running

| Option | Meaning |
| --- | --- |
| `--out` | Folder for all reports, overriding `out` in the spec |
| `--only a,b` | Run only these audits |
| `--rerun` | Run audits that already have a `report.json` (by default they are kept) |
| `--dry-run` | Print every `modeldiffr audit` command and stop |

Batch keeps going when one audit fails, and exits with `5` at the end if any did. Fix the cause and run the same command again: finished audits are skipped.

## index.json

`OUT/index.json` records every audit's command, status, exit code, run time, audit id, verdict and outcome, plus a summary:

```json
{
  "summary": {
    "audits": 11, "completed": 11, "failed": 0,
    "planted": 8, "detected": 7, "detection_rate": 0.875,
    "controls_clean": 3, "false_positives": 0, "false_positive_rate": 0.0
  }
}
```

Pass the folder to [`modeldiffr registry build`](registry.md) to publish the results.
