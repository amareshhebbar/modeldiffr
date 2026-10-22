---
title: Fingerprints and proof
description: How every report is tied to the exact models, prompts and results it describes.
---

# Fingerprints and proof

How every report is tied to the exact models, prompts and results it describes.

!!! success "New in 0.2"

    Every audit now fingerprints both models, gets an audit id, and can be checked by anyone with `modeldiffr verify`. Signing and public timestamps arrive in Phase 3, see the [roadmap](../roadmap.md).

A report is only evidence if a reader can confirm three things without trusting the author:

1. **Which models were compared.** Not a name on the Hub, which can be overwritten, but the exact weights.
2. **What was asked.** The exact suite items and settings.
3. **That nothing was edited.** The metrics follow from the per item results, and the results were not changed after the run.

Modeldiffr answers all three with content hashes, the same building blocks Git, software supply chain tools and blockchains use: SHA 256, canonical JSON and Merkle trees.

## What gets fingerprinted

| Object | How | Where in the report |
| --- | --- | --- |
| Weights | SHA 256 of every tensor's raw bytes, combined into a Merkle root | `fingerprints.*.weights.root` |
| Each tensor | Leaf hash of name, dtype, shape and data hash | `fingerprints.*.weights.leaves` |
| Vocabulary | Hash of every token and id plus added tokens, in canonical form | `fingerprints.*.tokenizer.vocab` |
| `tokenizer.json` | Hash of its canonical JSON, so whitespace and key order do not matter | `fingerprints.*.tokenizer.tokenizer_json` |
| Chat template | Hash of the template text | `fingerprints.*.tokenizer.chat_template` |
| Hub commit | The 40 character commit the files came from | `fingerprints.*.commit` |
| Suite | Merkle root over every question, choice set, prompt and text | `proof.suite_root` |
| Rendered prompts | Hash of the exact text each model received | `items.over_refusal.*[].rendered_sha256` |
| Results | Merkle root over every per item result | `proof.results_root` |
| Claims | Hash of audit id, results root, metrics, verdict, comparability and weights diff | `proof.statement_sha256` |

### Why a Merkle root for weights

A weights root does not depend on how the checkpoint is split into shard files or what the files are called. The same tensors give the same root whether they live in one file or twenty, and a `.bin` PyTorch checkpoint gives the same root as the same weights in safetensors.

Because every tensor has its own leaf, two fingerprints show exactly which tensors differ. Every report includes this as `weights_diff`:

```text
weights: 1 of 21 shared tensors changed, 0 added, 0 removed
```

This is useful on its own. A "4 bit near lossless" build where every tensor changed, a LoRA merge that only touched attention, or a fine tune that silently replaced the embedding matrix all show up before any benchmark runs.

The weights algorithm is `modeldiffr.weights/1`:

```text
leaf(tensor) = SHA256(0x00 || canonical_json({name, dtype, shape, data: sha256(raw bytes)}))
root         = RFC 6962 Merkle tree hash over leaves sorted by tensor name
```

Safetensors files are read directly, so every dtype works, including bfloat16 and float8, without loading the model into memory twice.

## The audit id

Before any model runs, Modeldiffr builds a **manifest**: both models' commits and fingerprints, the suite root, the settings (seed, resamples, decoding, template mode) and the Modeldiffr version. The audit id is the hash of that manifest in canonical JSON:

```text
audit id = "mdr1:" + SHA256(RFC 8785 canonical JSON of the manifest)
```

Two consequences:

* **Same inputs, same id.** Anyone auditing the same pair with the same suite and settings gets the same audit id, on any machine, before running anything. Duplicate work is visible and results can be compared across machines.
* **Any change to inputs changes the id.** A different commit, a different seed, a single changed suite item or tensor gives a different id.

The environment (Python version, platform, GPU) is recorded in the report but kept out of the manifest, so the id names the experiment, not the machine it ran on.

## Canonical JSON

Hashing JSON needs one exact byte form for each value. Modeldiffr uses [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785), the JSON Canonicalization Scheme: keys sorted by UTF 16 code units, no whitespace, numbers in the shortest form that round trips, as in JavaScript. The implementation passes the RFC's own test vectors.

## Comparable prompts

Unfair comparisons usually come from prompts, not weights. Before running, Modeldiffr compares the two tokenizers and chat templates:

| Situation | What happens |
| --- | --- |
| Same template | Each model renders its own prompt, which is identical anyway |
| Templates differ, same vocabulary | Both models get prompts rendered with one template (the base model's by default), so prompts are byte identical; a warning is recorded |
| Templates differ, different vocabulary | Each model uses its own template; a warning says part of any difference may come from the template |
| `--template base` forced with different vocabularies | The audit stops with exit code 3, because one tokenizer cannot read the other's special tokens |

Every generation item records the hash of the exact prompt each model received, so a reader can confirm the prompts were identical. Choose the behavior with `--template auto|base|derivative|own`.

Other checks, all recorded under `comparability.issues`: different special tokens, different dtypes, missing fingerprints, and byte identical weights.

## What verify checks

`modeldiffr verify report.json` recomputes everything that can be recomputed from the report itself:

| Check | Fails when |
| --- | --- |
| `schema` | A field is missing or has the wrong type |
| `audit_id` | The manifest does not hash to the audit id |
| `manifest_consistency` | Settings or fingerprints differ from what the manifest names |
| `suite` | The built in suite does not hash to the recorded root |
| `results_root` | Any per item result was edited |
| `metrics` | A metric, interval or flag does not follow from the items |
| `verdict` | The list of changed metrics does not match the metrics |
| `*_weights_leaves` | The tensor hashes do not give the weights root |
| `weights_diff` | The diff does not follow from the tensor hashes |
| `statement` | Any claim differs from the statement hash |
| `*_model_files` | With `--models`: the actual model files do not hash to the recorded root |

See [Verify a report](../guides/verify.md).

## What this proves and what it does not

!!! warning "Read this before relying on a report"

    A report that passes `verify` is **internally consistent and tied to exact model files**. It does **not** prove the author ran the models honestly: someone could write a consistent report by hand. Two things close that gap. Rerunning the audit, which gives the same audit id and, on the same hardware class, the same results. And signing, which arrives in Phase 3: a signed report says who vouches for it, and a transparency log entry says when.

## Coming next

| Phase | Adds |
| --- | --- |
| 3 | Sigstore signing, in toto attestations, Rekor transparency log, verification of OpenSSF model signatures |
| 3 | Optional public timestamps: OpenTimestamps on Bitcoin, Ethereum Attestation Service on an L2. Only hashes go on chain |
| 3 | Commit and reveal for private benchmark suites, so nobody can train on them before they are used |
| 3 | AI bill of materials export (CycloneDX and SPDX) |
