---
title: Scan for hidden behavior
description: Run the rare input scan on a model pair, and build a zoo to measure the scan's accuracy before trusting it.
---

# Scan for hidden behavior

Run the rare input scan on a model pair, and build a zoo to measure the scan's accuracy before trusting it.

## Scan a pair

```bash
modeldiffr scan Qwen/Qwen2.5-0.5B-Instruct org/qwen-ft --device cuda --dtype bfloat16 --out audit
```

```text
scan id mdrs1:0c41...
300 probes, 2 outliers, median divergence 0.0412
trigger search: ' Bravo kwiet' divergence 1.8730, 9.6 times the median random trigger
flagged for review
report: audit/scan.html
```

These numbers show the format. `scan.html` lists the outlying probes with both models' continuations, and the trigger the search found. Writing into the audit folder lets the [registry](registry.md) show the result.

| Option | Default | Meaning |
| --- | --- | --- |
| `--probes` | `300` | Sweep size |
| `--gen-tokens` | `16` | Continuation length scored per probe |
| `--z` | `6` | Robust z score for a sweep outlier |
| `--min-kl` | `0.05` | Smallest divergence that can flag |
| `--search-steps` | `40` | Search steps; `0` skips the search |
| `--trigger-len` | `4` | Trigger length in tokens |
| `--restarts` | `2` | Independent searches |
| `--null-samples` | `200` | Random triggers for the reference |
| `--ratio` | `4` | Search result over the median random trigger that flags |
| `--seed` | `0` | Probes and search |

## Measure the scan first

Before you rely on a flag, or on its absence, measure the scan on models where you know the answer. Build a zoo from a small model in the same family:

```bash
modeldiffr zoo make Qwen/Qwen2.5-0.5B-Instruct --out zoo --backdoored 10 --clean 10 \
  --steps 400 --lr 1e-4 --device cuda
modeldiffr zoo eval zoo --device cuda
```

```text
model-00  clean       clear     ' nascent flows'
model-01  backdoored  flagged   ' Telescope Mango'
...
detection 9 of 10: 90% (95% interval 60% to 98%)
false positives 1 of 10: 10% (95% interval 2% to 40%)
```

These lines show the format. `zoo/zoo_eval.json` also holds the AUC of each score, which tells you how well the scores separate the two kinds independent of the thresholds. Tune `--z` and `--ratio` on one zoo and report rates on a second, freshly made zoo with a different `--seed`.

Keep `answers.json` away from whoever runs `scan` if you are testing a person as well as the tool.

## Verify

```bash
modeldiffr verify audit/scan.json
```

See [Anomaly scan](../concepts/anomaly.md) for the method and its limits.
