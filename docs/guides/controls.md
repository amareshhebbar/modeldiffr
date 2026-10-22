---
title: Positive controls
description: Plant known changes in a copy of a model and check that the audit finds them, and that identical copies stay clean.
---

# Positive controls

Plant known changes in a copy of a model and check that the audit finds them, and that identical copies stay clean.

An audit that never flags anything is as useless as one that flags everything. Controls measure both rates on your own hardware, suite and settings before you publish a verdict about someone else's model.

## Make a control

```bash
modeldiffr controls make Qwen/Qwen2.5-0.5B-Instruct --out ctrl/noise-0.2 --kind noise --strength 0.2
```

```text
wrote ctrl/noise-0.2: noise 0.2 on 168 tensors
an audit against Qwen/Qwen2.5-0.5B-Instruct should find: change
```

The command reads the safetensors shards directly, perturbs the matching tensors, keeps their dtypes, copies config and tokenizer files, and writes `modeldiffr_control.json` with everything needed to reproduce it.

| Kind | Effect | `--strength` | Expected |
| --- | --- | --- | --- |
| `identity` | Byte for byte copy | ignored | no change |
| `noise` | Adds Gaussian noise | standard deviation as a share of each tensor's own | change |
| `scale` | Multiplies weights | factor (`1` means identity) | change |
| `zero` | Sets tensors to zero | ignored | change |
| `prune` | Zeroes the smallest weights by magnitude | share zeroed | change |

By default the attention and MLP projection matrices of every layer are touched, and embeddings and norms are left alone. Narrow it with a regular expression:

```bash
modeldiffr controls make Qwen/Qwen2.5-0.5B-Instruct --out ctrl/zero-l23 \
  --kind zero --match 'layers\.23\.mlp\.down_proj\.weight$'
```

Noise is seeded per tensor from `--seed` and the tensor name, so the same command always writes the same weights and the same weight root.

## Run a control study

[`examples/controls.yaml`](https://github.com/amareshhebbar/modeldiffr/blob/main/examples/controls.yaml) defines three identical copies and eight perturbations. Batch makes each control before auditing it:

```bash
modeldiffr batch examples/controls.yaml
```

```text
identity-seed0               done      no significant change  [clean]
identity-seed1               done      no significant change  [clean]
noise-0.05                   done      no significant change  [missed]
noise-0.20                   done      over_refusal_rate, mmlu_accuracy, output_divergence_kl  [detected]
...
10 of 11 audits complete, 0 failed; planted changes found 6 of 8 (75%), false positives 0 of 3 (0%)
```

The figures above illustrate the format. Run it to get yours.

Read a missed control as information, not failure: the smallest perturbation may genuinely change nothing measurable, which is what `modeldiffr power` predicts for a given suite size. Publish the study next to any verdict that depends on the suite being sensitive enough.

## What controls cannot tell you

Random noise is not a fine tune. A suite that finds noise can still miss a narrow, targeted change, such as a backdoor or a single removed refusal. That is what the representational layer and the anomaly scan address.
