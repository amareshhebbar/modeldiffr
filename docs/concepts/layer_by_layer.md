---
title: Layer by layer comparison
description: How Modeldiffr compares two models one layer at a time, why that works, and why benchmarks alone are not enough.
---

# Layer by layer comparison

Benchmarks tell you **that** a model changed. This page explains the tools that tell you **where** inside the model it changed.

## The short version

A language model is a stack of layers, like floors in a building. Text comes in at the bottom, every layer reads what the layer below it wrote, changes it a little, and passes it up. The top layer turns the result into the next word.

If you give two models the exact same text, and they produce the exact same output at layer 5, then nothing before layer 5 is different in any way that matters for that text. If they start to differ at layer 6, the change starts at layer 6.

Modeldiffr does exactly this. It reads both models one layer at a time and tells you where they start to split, and by how much.

## Two ways to compare layers

| View | Command | What it looks at | Runs the model? | Cost |
| --- | --- | --- | --- | --- |
| Weights view | inside every `audit`, also `fingerprint` | The stored numbers of each tensor | No | Reads each file once |
| Hidden states view | `modeldiffr layers` | What each layer outputs on real text | Yes, one forward pass per model | Seconds to minutes |

They answer different questions. The weights view says **which parts of the file were edited**. The hidden states view says **which parts of the thinking changed**. A small edit in the weights can cause a big change in the hidden states, and a big edit (like quantization) can cause only a small one.

## The weights view

### What it does

1. Open both models' weight files (safetensors, PyTorch `.bin`, or GGUF).
2. For every tensor, compute a SHA 256 hash of its raw bytes, together with its name, dtype and shape.
3. Compare the two lists by tensor name.

Every tensor ends up in one of four groups: **unchanged**, **changed**, **added** (only in the derivative), or **removed** (only in the base). Every audit report has this in `weights_diff`:

```text
weights: 12 of 290 shared tensors changed, 0 added, 0 removed
```

Tensor names include the layer number, for example `model.layers.14.self_attn.q_proj.weight`, so the list of changed tensors is already a layer by layer map of the edit.

### How to read it

| What you see | What it usually means |
| --- | --- |
| Nothing changed | The "new" model is a copy of the base. Worth knowing before you spend a GPU hour |
| Only `q_proj`, `k_proj`, `v_proj`, `o_proj` changed | A LoRA on attention was merged in |
| Only a few layers changed | A targeted edit, such as ROME, or a refusal direction removed from a few layers |
| Every tensor changed | Full fine tune, quantization, or a merge |
| `embed_tokens` or `lm_head` changed, plus added rows | New tokens were added to the vocabulary |
| Tensors added or removed | The architecture changed, for example pruned layers |

### Why this works

A hash changes completely if even one bit of a tensor changes, and stays the same if nothing changed. So "same hash" means "same tensor", with no doubt. That makes this view exact and fast.

### What it cannot tell you

It only says **changed or not**. It does not yet say **by how much**. A tensor that moved by 0.0001 and one that was replaced completely look the same here. That is what the hidden states view is for. Measuring the size of each weight change is on the [pending list](../roadmap.md#still-pending).

## The hidden states view

### What it does, step by step

1. **Pick some text.** By default a small built in set. You can pass your own with `--corpus`: a `.txt` file, a `.jsonl` file, or a Hugging Face dataset.
2. **Tokenize it with both tokenizers.** If a text turns into different token ids in the two models, it is skipped and counted. Both models must see exactly the same tokens, otherwise we would be comparing different inputs.
3. **Run both models on the same tokens.** A small hook on each layer saves its output (the "hidden state", also called the residual stream) for every token.
4. **Drop the first token.** The first position in most models has huge activation values that have nothing to do with meaning. Keeping it would make every number below look worse than it is.
5. **For each layer, line up the two outputs token by token** and compute five numbers.

### The five numbers

Write `b` for the base model's output vector for one token at one layer, and `d` for the derivative's output for the same token at the same layer.

| Number | How it is computed | Plain meaning | Identical models |
| --- | --- | --- | --- |
| `cka` | Linear centered kernel alignment over all tokens | Do both layers arrange the information the same way? It ignores rotations and scaling, so it only drops when the structure really changes | 1 |
| `cosine` | Average of `cos(b, d)` over tokens | Do the two vectors point the same way? | 1 |
| `relative_change` | Average of `|d - b| / |b|` over tokens | How big is the difference, as a share of the base output? 0.15 means about 15% | 0 |
| `mean_shift` | `|mean(d) - mean(b)| / |mean(b)|` | Did the whole layer move in one shared direction? | 0 |
| `norm_ratio` | Average `|d|` divided by average `|b|` | Did outputs get louder (above 1) or quieter (below 1)? | 1 |

The command prints the layer with the largest `relative_change` at the end, because that is usually the best place to look next.

### Why each number is there

One number is not enough, because different kinds of edits leave different marks:

* **CKA** catches a change in structure. It stays near 1 if the derivative just rotated or rescaled the space, which matters because a rotation does not really change what the layer knows.
* **Cosine** and **relative change** catch changes on single tokens, even when the overall structure is the same.
* **Mean shift** catches edits that push every token the same way. Steering vectors and refusal removal look like this.
* **Norm ratio** catches quantization and merge side effects that make activations bigger or smaller everywhere.

### How to read the pattern across layers

Plot or scan the numbers from layer 0 upward. The shape tells a story:

| Pattern | Likely cause |
| --- | --- |
| Flat at 1 and 0 all the way up | No real change on this text. Try text closer to what the derivative was trained on |
| Small, even noise at every layer | Quantization or a lower precision dtype. Every layer loses a little precision |
| Flat, then a clear jump at one layer that stays high | A fine tune or edit that starts working at that layer |
| Big `mean_shift` at a few layers, other numbers fine | One direction was added or removed, as in abliteration or steering |
| Grows steadily toward the top | Small early changes that add up as they travel through the network |
| `norm_ratio` far from 1 | Scaling problems, common in merges |

### Why this works

The key idea is **same input, compare at every step**. Because both models read the exact same token ids, the only reason their hidden states can differ is that their weights differ. And because each layer only sees what the layers below it produced, the first layer that differs is the earliest point where the edit has an effect.

This is the same trick as debugging a program by printing variables after every line, in two versions of the program, and finding the first line where they disagree.

### Why it is needed

* **Benchmarks can hide real changes.** Two models can get the same MMLU score while one of them has a completely different refusal circuit inside. Benchmark scores average away what happens in the middle of the network.
* **It is cheap.** One forward pass per model on a few hundred texts. No training, no labels, no GPU hours.
* **It points the expensive tools at the right place.** Crosscoders (`modeldiffr features`) and causal patching (`modeldiffr causal`) work on one layer at a time and can take hours. Running them on the wrong layer wastes all of that. `layers` tells you which layer to pick.
* **It catches quiet damage.** A quant that looks fine on benchmarks but is noisy in one layer will show it here, before users find it on some rare input.

## Directions: checking one concept across layers

`modeldiffr directions` is a focused version of the same idea. You give it two sets of prompts, for example prompts the base refuses and prompts it answers. For every layer it:

1. Averages the last token output of each set, in each model.
2. Takes the difference. That difference is the "direction" for this concept, such as refusal.
3. Compares the base direction with the derivative direction (`cosine`).
4. Measures how far apart the two prompt sets sit along the base direction, in each model (`separation`).

If the ratio of separations is well below 1, the derivative has weakened that concept at that layer. An abliterated model usually keeps a similar direction but with much smaller separation. This method comes from Arditi et al., 2024.

## Commands

```bash
modeldiffr layers BASE DERIVATIVE
modeldiffr layers BASE DERIVATIVE --layers 8-20 --corpus data.jsonl --texts 2000 --json
modeldiffr directions BASE DERIVATIVE --positive refused.txt --negative answered.txt --layers 8-20
```

`--layers` takes `all`, `middle`, a number (negative counts from the end), a range like `2-5`, or a comma separated mix. `--json` prints the raw numbers for your own plots. All options are in the [CLI reference](../reference/cli/interp.md).

## Limits

* Both models must use the same tokenizer. Texts that tokenize differently are skipped.
* Both models must load with transformers. GGUF builds cannot be compared here yet.
* The numbers describe the text you give. A medical fine tune compared on cooking recipes may look unchanged. Use text close to what the derivative was trained for, plus some general text.
* The default built in text is small. For a real decision, pass a corpus with a few thousand texts.
* The layer numbers have no confidence intervals yet, and are not saved as a signed, verifiable file like audit reports. See [still pending](../roadmap.md#still-pending).
* Finding where a change happens is not the same as knowing what it does. Use [features](representational.md) and [causal tests](causal.md) for that.

## References

* Kornblith, S. et al. *Similarity of Neural Network Representations Revisited.* ICML 2019. The source of CKA.
* Arditi, A. et al. *Refusal in Language Models Is Mediated by a Single Direction.* 2024.