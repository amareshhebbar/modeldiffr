---
title: Find changed features
description: Locate the layers a derivative changed, check a concept direction, and train a crosscoder to list new, lost and shifted features.
---

# Find changed features

Locate the layers a derivative changed, check a concept direction, and train a crosscoder to list new, lost and shifted features.

```bash
pip install "modeldiffr[hf,tasks]"
```

## 1. Find the layers that moved

```bash
modeldiffr layers Qwen/Qwen2.5-0.5B-Instruct huihui-ai/Qwen2.5-0.5B-Instruct-abliterated-v3 \
  --corpus builtin --dtype float32
```

```text
1850 tokens from 76 texts (0 skipped)
layer      CKA   cosine  rel change  mean shift  norm ratio
    0   1.0000   1.0000      0.0000      0.0000      1.0000
  ...
   14   0.9871   0.9802      0.1543      0.0611      0.9930
  ...
largest change at layer 14
```

The numbers above show the format; yours depend on the pair. `--corpus` takes `builtin` (the quick suite's texts), a `.jsonl` file with a `text` field (`--field` to change it), a `.txt` file with texts separated by blank lines, or `hf:DATASET[:CONFIG]:SPLIT` to stream from the Hub.

## 2. Check a direction you care about

```bash
modeldiffr directions BASE DERIVATIVE --positive harmful.txt --negative harmless.txt --layers 8-20
```

| Column | Meaning |
| --- | --- |
| `cosine` | Agreement between the two models' directions |
| `base sep` | Separation of the two prompt sets along the base direction, in the base |
| `deriv sep` | The same separation, in the derivative |
| `ratio` | `deriv sep / base sep`; well below 1 means the concept was weakened |

Use your own prompt sets. Modeldiffr does not ship harmful prompts.

## 3. Train a crosscoder

```bash
modeldiffr features BASE DERIVATIVE --layer 14 \
  --corpus hf:HuggingFaceFW/fineweb-edu:sample-10BT:train --texts 20000 --max-tokens 200000 \
  --dict-size 16384 --k 64 --steps 20000 --dtype bfloat16 --device cuda \
  --out audit --report audit/report.json
```

```text
features id mdrf1:a77a8e2a...
layer 14: 41 new, 12 lost, 230 shifted, 15233 shared, 868 never active
variance explained base 0.871, derivative 0.866
report: audit/features.html
```

Writing into the audit folder with `--report` links the two, and the [registry](registry.md) then shows the feature counts on the audit's page.

| Setting | Small model on a CPU | 7B on one GPU |
| --- | --- | --- |
| `--max-tokens` | 20,000 | 200,000 to 1,000,000 |
| `--dict-size` | 2,048 | 16,384 to 65,536 |
| `--k` | 32 | 64 to 128 |
| `--steps` | 2,000 | 20,000 or more |
| `--batch-size` | 1,024 | 4,096 |

Activations need `tokens × hidden size × 8` bytes of memory: 200,000 tokens of a 3,584 wide model is 5.7 GB.

Add `--variant delta` for a narrow fine tune, and `--label-api URL --label-model NAME` for automatic labels from any OpenAI compatible server (the key comes from `MODELDIFFR_API_KEY` or `OPENAI_API_KEY`).

## 4. Read the page

`features.html` shows the class counts, a histogram of where each feature's decoder norm lives, fit statistics, and for each class a list of features with the contexts where they fire most. Treat a `derivative_only` feature with a clear pattern of examples as a lead to test with causal checks, not as a conclusion.

## 5. Verify

```bash
modeldiffr verify audit/features.json
```

```text
PASS  id                         mdrf1:a77a8e2a...
PASS  result_hash                results match their hash
PASS  crosscoder.safetensors     matches its hash
PASS  classes                    16384 features classified
```

See [Representational layer](../concepts/representational.md) for the method and its limits.
