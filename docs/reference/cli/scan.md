---
title: scan, zoo
description: Commands for the anomaly scan and the model zoo.
---

# scan, zoo

Commands for the anomaly scan and the model zoo. Both need the `hf` extra.

## scan

```text
usage: modeldiffr scan [--device DEVICE] [--dtype DTYPE] [--trust-remote-code] [--no-weight-hash]
                       [--out OUT] [--probes N] [--gen-tokens N] [--z Z] [--min-kl KL]
                       [--ratio R] [--search-steps N] [--trigger-len N] [--restarts N]
                       [--null-samples N] [--seed SEED] base derivative
```

Writes `scan.json` and `scan.html` to `--out` (default `modeldiffr_scan`). Defaults are listed in [Scan for hidden behavior](../../guides/scan.md#scan-a-pair). Both models must share a vocabulary.

## zoo make

```text
usage: modeldiffr zoo make --out OUT [--backdoored N] [--clean N] [--steps N] [--lr LR]
                           [--batch N] [--trigger-words N] [--poison-rate P]
                           [--device DEVICE] [--seed SEED] base
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--backdoored`, `--clean` | `2`, `2` | Models of each kind |
| `--steps`, `--lr`, `--batch` | `300`, `1e-4`, `8` | Full fine tuning per model |
| `--trigger-words` | `2` | Words per trigger |
| `--poison-rate` | `0.3` | Share of training examples that carry the trigger |

Writes `model-NN/` folders, `zoo.json` and `answers.json`.

## zoo eval

```text
usage: modeldiffr zoo eval [--device DEVICE] [scan options] zoo
```

Scans every model, writes `scans/model-NN/` and `zoo_eval.json`, and prints detection and false positive rates with 95% intervals.
