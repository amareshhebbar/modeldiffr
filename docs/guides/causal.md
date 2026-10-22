---
title: Test what drives a change
description: Patch layers and features from the derivative into the base and measure how much of the behavioral change follows.
---

# Test what drives a change

Patch layers and features from the derivative into the base and measure how much of the behavioral change follows.

## 1. Start from an audit with a change

```bash
modeldiffr audit Qwen/Qwen2.5-1.5B-Instruct org/qwen-ft --suite lite --tasks mmlu,arc_challenge --out audit
```

Causal checks need a change on multiple choice items. If the audit shows none, there is nothing to explain.

## 2. Patch whole layers

```bash
for L in 4 8 12 16 20 24; do
  modeldiffr causal Qwen/Qwen2.5-1.5B-Instruct org/qwen-ft --layer $L \
    --suite lite --tasks mmlu --limit 300 --dtype bfloat16 --device cuda --out causal/L$L
done
```

```text
causal id mdrc1:5b03...
probability of the correct option: base 0.5512, derivative 0.5207, change -0.0305
patch_layer                67.3%  [52.1, 84.0]
reverse_layer              58.9%  [41.7, 77.5]
steer_0.5                  21.4%  [9.8, 33.0]
steer_1                    39.0%  [24.2, 55.1]
steer_2                    61.7%  [40.3, 86.2]
report: causal/L12/causal.html
```

These figures show the format. The layer where `patch_layer` reaches about 100% is where the change is complete.

## 3. Patch features

Train a crosscoder at a layer from step 2 (see [Find changed features](features.md)), then point `causal` at its folder:

```bash
modeldiffr features BASE DERIVATIVE --layer 12 --out audit --report audit/report.json ...
modeldiffr causal BASE DERIVATIVE --layer 12 --suite lite --tasks mmlu --limit 300 \
  --features audit --top 10,50,200 --report audit/report.json --out audit
```

The run fails if the crosscoder was trained on another layer or its weights do not match `features.json`. Writing into the audit folder lets the [registry](registry.md) show the share on the audit's page.

## 4. Verify

```bash
modeldiffr verify audit/causal.json
```

See [Causal layer](../concepts/causal.md) for the definitions and limits.
