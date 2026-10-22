---
title: layers, directions, features, causal
description: Commands for the representational and causal layers.
---

# layers, directions, features, causal

Commands for the representational and causal layers. All four need the `hf` extra and load both models with transformers.

## Shared options

| Option | Default | Meaning |
| --- | --- | --- |
| `--device` | `auto` | `cpu`, `cuda`, `cuda:0` or `mps` |
| `--dtype` | `auto` | `float32`, `float16` or `bfloat16` |
| `--base-revision`, `--derivative-revision` | latest | Pin revisions; Hub URLs with `/tree/REF` also work |
| `--trust-remote-code` | off | Allow custom model code |

Corpus options for `layers` and `features`:

| Option | Default | Meaning |
| --- | --- | --- |
| `--corpus` | `builtin` | `builtin`, a `.jsonl` or `.txt` file, or `hf:DATASET[:CONFIG]:SPLIT` |
| `--field` | `text` | Field with the text |
| `--texts` | 500 for layers, 5000 for features | Texts to read |
| `--max-tokens` | 20,000 for layers, 50,000 for features | Tokens to capture |
| `--max-length` | `256` | Tokens per text |

## layers

```text
usage: modeldiffr layers [--layers LAYERS] [--json] base derivative
```

`--layers` takes `all`, `middle`, an index (negative counts from the end), ranges such as `2-5`, or a comma separated mix.

## directions

```text
usage: modeldiffr directions --positive FILE --negative FILE [--layers LAYERS] [--json] base derivative
```

## features

```text
usage: modeldiffr features [--layer LAYER] [--dict-size N] [--k K] [--variant {standard,delta}]
                           [--steps N] [--batch-size N] [--lr LR] [--seed SEED]
                           [--per-class N] [--examples N] [--report REPORT]
                           [--label-api URL] [--label-model NAME] [--no-weight-hash]
                           [--out OUT] base derivative
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--layer` | `middle` | One layer |
| `--dict-size` | `4096` | Features in the crosscoder |
| `--k` | `32` | Average active features per token |
| `--variant` | `standard` | `delta` ties the decoders and penalizes the difference |
| `--steps`, `--batch-size`, `--lr`, `--seed` | `2000`, `2048`, `5e-4`, `0` | Training |
| `--per-class` | `20` | Features per class shown with examples |
| `--examples` | `8` | Top contexts per feature |
| `--report` | none | Link to an audit and check the weights match |
| `--label-api`, `--label-model` | none | Automatic, unverified labels |
| `--out` | `modeldiffr_features` | Folder for `features.json`, `features.html` and `crosscoder.safetensors` |

## causal

```text
usage: modeldiffr causal [--layer LAYER] [--suite SUITE] [--tasks TASKS] [--limit N]
                         [--data-dir DIR] [--features DIR] [--top 10,50,200]
                         [--alphas 0.5,1,2] [--resamples N] [--seed SEED]
                         [--report REPORT] [--no-weight-hash] [--out OUT] base derivative
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--layer` | `middle` | One layer |
| `--suite`, `--tasks`, `--limit`, `--data-dir` | `quick`, all, `200` | Items to use; only multiple choice tasks are kept |
| `--features` | none | Folder with `features.json` and `crosscoder.safetensors` from the same layer |
| `--top` | `10,50,200` | Feature set sizes to patch |
| `--alphas` | `0.5,1,2` | Steering strengths; empty to skip |
| `--resamples`, `--seed` | `2000`, `0` | Bootstrap |
| `--report` | none | Link to an audit and check the weights match |
| `--out` | `modeldiffr_causal` | Folder for `causal.json` and `causal.html` |

`modeldiffr verify features.json` and `modeldiffr verify causal.json` check these files. Errors such as a wrong layer, a missing corpus or models with different vocabularies exit with `2`.
