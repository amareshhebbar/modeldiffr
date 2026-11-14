---
title: Fingerprints and proof
description: How every report is locked to the exact models, prompts and results it describes, so nobody has to trust the author.
---

# Fingerprints and proof

How every report is locked to the exact models, prompts and results it describes.

## Why this exists

A benchmark table on a model card is a claim. You cannot tell which exact weights were run, which questions were asked, or whether a number was edited. A report is only real evidence if a reader can check three things **without trusting the author**:

1. **Which models.** Not a name on the Hub, which anyone can overwrite, but the exact weights.
2. **What was asked.** The exact questions and settings.
3. **Nothing was edited.** The metrics really follow from the per question results, and those results were not changed later.

Modeldiffr does this with hashes, the same tools Git and software supply chain systems use: SHA 256, canonical JSON and Merkle trees.

## What gets fingerprinted

| Thing | How | Where in the report |
| --- | --- | --- |
| Weights | SHA 256 of every tensor's raw bytes, combined into one root hash | `fingerprints.*.weights.root` |
| Each tensor | Hash of its name, dtype, shape and data hash | `fingerprints.*.weights.leaves` |
| Vocabulary | Hash of every token and id plus added tokens | `fingerprints.*.tokenizer.vocab` |
| `tokenizer.json` | Hash of its canonical JSON, so spacing and key order do not matter | `fingerprints.*.tokenizer.tokenizer_json` |
| Chat template | Hash of the template text | `fingerprints.*.tokenizer.chat_template` |
| Hub commit | The 40 character commit the files came from | `fingerprints.*.commit` |
| Suite | One root hash over every question, option, prompt and text | `proof.suite_root` |
| Rendered prompts | Hash of the exact text each model got | `items.over_refusal.*[].rendered_sha256` |
| Results | One root hash over every per question result | `proof.results_root` |
| Claims | Hash of the audit id, results root, metrics, verdict, comparability and weights diff | `proof.statement_sha256` |

### Why a Merkle tree for weights

A Merkle tree combines many hashes into one root, in a way where you can still see which leaf changed.

* The weights root does **not** depend on how the checkpoint is split into files, or what those files are called. One file or twenty, `.bin` or safetensors, same tensors give the same root.
* Because every tensor has its own leaf, comparing two fingerprints shows exactly which tensors differ. Every report has this as `weights_diff`:

```text
weights: 1 of 21 shared tensors changed, 0 added, 0 removed
```

That alone is useful. A "4 bit near lossless" build where every tensor changed, a LoRA merge that only touched attention, or a fine tune that quietly replaced the embedding matrix all show up before any benchmark runs. See the [weights view](layer_by_layer.md#the-weights-view).

The algorithm, called `modeldiffr.weights/1`:

```text
leaf(tensor) = SHA256(0x00 || canonical_json({name, dtype, shape, data: sha256(raw bytes)}))
root         = RFC 6962 Merkle tree hash over leaves sorted by tensor name
```

Safetensors files are read directly, so every dtype works (including bfloat16 and float8) without loading the model twice.

## The audit id

Before any model runs, Modeldiffr writes a **manifest**: both models' commits and fingerprints, the suite root, every setting (seed, resamples, decoding, template mode) and the Modeldiffr version. The audit id is the hash of that manifest:

```text
audit id = "mdr1:" + SHA256(RFC 8785 canonical JSON of the manifest)
```

What that gives you:

* **Same inputs, same id.** Anyone auditing the same pair with the same suite and settings gets the same id, on any machine, before running anything. Duplicate work is easy to spot, and results from different machines can be compared.
* **Any change, new id.** A different commit, seed, question or tensor gives a different id.

The environment (Python version, platform, GPU) is saved in the report but kept out of the manifest. The id names the experiment, not the machine.

## Canonical JSON

To hash JSON, every value needs exactly one byte form. Modeldiffr uses [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785): keys sorted, no spaces, numbers in their shortest exact form. The implementation passes the RFC's own test cases.

## Fair prompts { #comparable-prompts }

Unfair comparisons usually come from prompts, not weights. Before running, Modeldiffr compares the two tokenizers and chat templates:

| Situation | What happens |
| --- | --- |
| Same template | Each model renders its own prompt, which is identical anyway |
| Different templates, same vocabulary | Both get prompts rendered with one template (the base's by default), so prompts are byte identical. A warning is saved |
| Different templates, different vocabulary | Each uses its own template. A warning says part of any difference may come from the template |
| `--template base` forced with different vocabularies | The audit stops with exit code 3, because one tokenizer cannot read the other's special tokens |

Every generated item saves the hash of the exact prompt each model got, so a reader can confirm they were identical. Pick the behavior with `--template auto|base|derivative|own`.

Other checks, saved under `comparability.issues`: different special tokens, different dtypes, missing fingerprints, and weights that are byte identical.

## What verify checks

`modeldiffr verify report.json` recomputes everything it can from the report itself:

| Check | Fails when |
| --- | --- |
| `schema` | A field is missing or has the wrong type |
| `audit_id` | The manifest does not hash to the audit id |
| `manifest_consistency` | Settings or fingerprints differ from the manifest |
| `suite` | The built in suite does not hash to the saved root |
| `results_root` | Any per question result was edited |
| `metrics` | A metric, range or flag does not follow from the results |
| `verdict` | The list of changed metrics does not match the metrics |
| `*_weights_leaves` | The tensor hashes do not give the weights root |
| `weights_diff` | The diff does not follow from the tensor hashes |
| `statement` | Any claim differs from the statement hash |
| `*_model_files` | With `--models`: the real model files do not hash to the saved root |

See [Verify a report](../guides/verify.md).

## What this proves, and what it does not

!!! warning "Read this before relying on a report"

    A report that passes `verify` is **consistent** and **tied to exact model files**. It does **not** prove the author really ran the models: someone could write a consistent report by hand. Two things close that gap. Rerunning the audit, which gives the same audit id and, on the same kind of hardware, the same results. And signing, which says who vouches for the report, plus a timestamp that says when. See [Attestations](attestation.md).