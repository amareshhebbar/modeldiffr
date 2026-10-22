---
title: Reproducibility
description: Make every audit rerunnable with the same result.
---

# Reproducibility

Make every audit rerunnable with the same result.

An audit is only useful if someone else can rerun it and get the same numbers. Modeldiffr records what it needs in `report.json`, but you control the inputs.

## Checklist

### 1. Pin model revisions

Hugging Face model ids point at a moving branch. Pin the exact commit.
```bash
modeldiffr audit org/base org/derivative \
  --base-revision BASE_COMMIT_SHA \
  --derivative-revision DERIVATIVE_COMMIT_SHA
```
When no revision is given, Modeldiffr records the resolved commit hash from the model config in `base.revision` and `derivative.revision`. Either way, the weights are fingerprinted, so the report names the exact tensors even if a branch moves later.

### 2. Fix the dtype

`--dtype auto` follows each checkpoint's config, which can differ between models. Set it explicitly.
```bash
--dtype bfloat16
```

### 3. Fix the seed and resamples

```bash
--seed 0 --resamples 2000
```

### 4. Pin the Modeldiffr version

```bash
pip install "modeldiffr[hf]==0.2.0"
```
The report stores `modeldiffr_version` and `schema_version`.

### 5. Keep the hardware class

Kernels differ across GPU generations and between CPU and GPU. Log probabilities can shift in the last digits, which can flip a borderline capability item. The report stores `device` and `environment.platform`.

## What is deterministic

| Part | Deterministic | Why |
| --- | --- | --- |
| Capability scoring | Yes, on the same hardware | Forward pass only, no sampling |
| Over refusal generation | Yes, on the same hardware | Greedy decoding, `do_sample=False` |
| Divergence | Yes, on the same hardware | Forward pass only |
| Bootstrap | Yes, everywhere | Seeded `random.Random` |

## The audit id

Every report has an `audit_id`, computed from both models' fingerprints, the suite and the settings before anything runs. Two people who run the same audit get the same id. If their `results_root` also matches, they got identical per item results. See [Fingerprints and proof](../concepts/proof.md).

## Fields to cite

When you publish an audit, include the full `report.json` so others can run [`modeldiffr verify`](verify.md). At minimum quote:

* `audit_id`

* `base.model_id`, `base.revision`
* `derivative.model_id`, `derivative.revision`
* `suite.name`, `settings`
* `modeldiffr_version`, `schema_version`
