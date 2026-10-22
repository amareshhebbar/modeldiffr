---
title: Report schema
description: Every field in report.json, schema version 0.3.
---

# Report schema

Every field in report.json, schema version 0.3.

!!! warning

    Schema `0.3` is a preview. Fields may change before v1.0. Always check `schema_version` before parsing. The machine readable JSON Schema ships inside the package: `modeldiffr.proof.verify.load_schema()`.

## Top level

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Report format version, `"0.3"` |
| `modeldiffr_version` | string | Package version that produced the report |
| `audit_id` | string | `mdr1:` plus the SHA 256 of the canonical manifest. Same inputs give the same id |
| `created_at` | string | UTC time in ISO 8601, to the second. Not part of the audit id |
| `suite` | object | `name`, `root` (Merkle root of the suite items), `notes` |
| `settings` | object | See [Settings](#settings) |
| `environment` | object | `python` and `platform`. Not part of the audit id |
| `base` | object | Backend metadata, see [Model metadata](#model-metadata) |
| `derivative` | object | Same shape as `base` |
| `manifest` | object | Everything the audit id is computed from, see [Manifest](#manifest) |
| `fingerprints` | object | `base` and `derivative`, see [Fingerprints](#fingerprints). `null` per side when the backend does not report them |
| `comparability` | object | `ok`, `template_mode`, `issues`, see [Comparability](#comparability) |
| `weights_diff` | object or null | Tensor level difference, see [Weights diff](#weights-diff) |
| `plan` | object | Items per task and detectable change, see [Plan](#plan) |
| `metrics` | object[] | One entry per metric, see [Metric object](#metric-object) |
| `verdict` | object | `changed` (significant and not negligible), `negligible`, and `any_change` |
| `notes` | string[] | Run notes, for example a skipped metric or unhashed weights |
| `items` | object | Per item results, see [Items](#items) |
| `proof` | object | Hashes that tie the report together, see [Proof](#proof) |
| `wall_time_seconds` | number | Time spent in `run_audit`, excluding model loading |

## Settings

| Field | Type | Meaning |
| --- | --- | --- |
| `seed` | integer | Bootstrap seed |
| `n_resamples` | integer | Bootstrap resamples |
| `decoding` | string | Always `"greedy"` |
| `template_mode` | string | `base`, `derivative` or `own`: whose chat template rendered generation prompts |
| `weights_hashed` | boolean | False when the audit ran with `--no-weight-hash` |
| `refusal_detector` | string | `keyword` or `hf:MODEL_ID` |
| `allow_code_execution` | boolean | Whether `humaneval` was allowed to run |
| `fdr_q` | number | False discovery rate target |
| `context_limit` | integer or null | Smaller context window of the two models, used to filter needle documents |

## Model metadata

For `HFBackend`: `model_id`, `revision` (pinned or resolved commit), `architecture`, `parameters`, `dtype`, `device`, `has_chat_template`. Custom backends may return any object with at least `model_id`.

## Manifest

```json
{
  "schema": "modeldiffr.manifest/2",
  "base": {
    "model_id": "Qwen/Qwen2.5-0.5B-Instruct",
    "revision": "7ae557604adf67be50417f59c2c2f167def9a775",
    "commit": "7ae557604adf67be50417f59c2c2f167def9a775",
    "weights_root": "sha256:4b1e...",
    "weights_algorithm": "modeldiffr.weights/1",
    "tokenizer_vocab": "sha256:51d2...",
    "tokenizer_json": "sha256:a8c0...",
    "chat_template": "sha256:0e77..."
  },
  "derivative": {},
  "suite": {
    "name": "standard",
    "root": "sha256:66b3...",
    "items": 4120,
    "tasks": [
      { "name": "mmlu", "kind": "multiple_choice", "source": { "path": "cais/mmlu", "config": "all", "split": "test", "revision": "c30699e8356da336a370243923dbaf21066bb9fe" }, "items": 1000, "max_new_tokens": 0 }
    ]
  },
  "settings": { "seed": 0, "n_resamples": 2000, "decoding": "greedy", "template_mode": "own", "weights_hashed": true, "refusal_detector": "keyword", "allow_code_execution": false, "fdr_q": 0.05, "context_limit": 32768 },
  "code": { "package": "modeldiffr", "version": "0.3.0" }
}
```

`derivative` has the same shape as `base`. Values are `null` when unknown, for example `commit` for a local directory.

## Fingerprints

| Field | Type | Meaning |
| --- | --- | --- |
| `commit` | string or null | Hub commit the files came from |
| `tokenizer.algorithm` | string | `modeldiffr.tokenizer/1` |
| `tokenizer.vocab` | string | Hash of every token and id plus added tokens |
| `tokenizer.vocab_size` | integer | Number of tokens |
| `tokenizer.special_tokens` | object | `bos_token`, `eos_token`, `pad_token`, `unk_token` |
| `tokenizer.chat_template` | string or null | Hash of the template text |
| `tokenizer.tokenizer_json` | string or null | Hash of the canonical `tokenizer.json` |
| `weights` | object or null | `null` with `--no-weight-hash` or unsupported formats |
| `weights.algorithm` | string | `modeldiffr.weights/1` |
| `weights.root` | string | Merkle root over all tensors |
| `weights.tensors` | integer | Number of tensors |
| `weights.bytes` | integer | Total tensor bytes |
| `weights.format` | string | `safetensors` or `pytorch` |
| `weights.leaves` | object | Tensor name to leaf hash (64 hex characters) |

## Comparability

```json
{
  "ok": true,
  "template_mode": "base",
  "issues": [
    { "level": "warning", "code": "chat_template_mismatch", "message": "The chat templates differ. Both models received prompts rendered with the base model's template, so prompts are identical." }
  ]
}
```

| Code | Level | Meaning |
| --- | --- | --- |
| `chat_template_mismatch` | warning | Templates differ; the message says how prompts were rendered |
| `shared_template_needs_same_vocab` | error | A shared template was forced but the tokenizers differ; the audit does not run |
| `vocab_mismatch` | info | Tokenizers differ; divergence is skipped |
| `special_tokens_mismatch` | warning | bos, eos, pad or unk differ |
| `dtype_mismatch` | warning | The models run in different dtypes |
| `weights_identical` | info | Both models have byte identical weights |
| `missing_fingerprint` | warning | A backend reports no fingerprints |

## Weights diff

| Field | Type | Meaning |
| --- | --- | --- |
| `identical` | boolean | No tensor changed, was added or removed |
| `shared` | integer | Tensors present in both models |
| `changed_count`, `added_count`, `removed_count`, `unchanged_count` | integer | Counts |
| `changed`, `added`, `removed` | string[] | Tensor names, at most 200 each |
| `truncated` | boolean | True when a list was cut at 200 |

## Metric object

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | For example `mmlu_accuracy`; see [Metrics](../concepts/metrics.md) |
| `description` | string | One sentence description |
| `higher_is_better` | boolean | Direction of improvement |
| `directional` | boolean | False when the metric has no better direction |
| `n` | integer | Number of items |
| `base_mean`, `derivative_mean` | number | Means |
| `delta` | number | Mean difference |
| `ci_low`, `ci_high` | number | Interval bounds |
| `confidence` | number | Interval level |
| `p_value` | number | Two sided bootstrap p value |
| `significant_raw` | boolean | The interval excludes zero |
| `significant` | boolean | Also passes the false discovery rate correction |
| `negligible` | boolean | Significant but smaller than `spec.min_effect` |
| `min_effect` | number | Only on `output_divergence_kl` |
| `spec` | object | `name`, `description`, `task`, `field`, `statistic` (`mean` or `ece`), `test` (`paired` or `one_sample`), `higher_is_better`, `directional`, `min_effect`. `verify` recomputes the metric from this and the items |

## Plan

```json
{
  "tasks": [
    { "task": "mmlu", "items": 1000, "loglik_calls": 4000, "generations": 0, "max_new_tokens": 0, "min_detectable_effect": 0.0443 }
  ],
  "estimated_seconds": 1840.5
}
```

`estimated_seconds` is `null` unless the audit ran with `--estimate`.

## Items

One entry per task. Paired tasks have aligned `base` and `derivative` lists; `divergence` has a single `pair` list.

```json
{
  "mmlu": {
    "base": [
      { "id": "1203", "predicted": 2, "expected": 2, "correct": 1.0, "confidence": 0.91, "score": 1.0 }
    ],
    "derivative": []
  },
  "gsm8k": {
    "base": [
      { "id": "17", "rendered_sha256": "sha256:9c1f...", "response": "...", "extracted": 18.0, "expected": 18.0, "score": 1.0 }
    ],
    "derivative": []
  },
  "divergence": {
    "pair": [
      { "id": "builtin:0", "text": "The library opens at nine...", "kl": 0.0213 }
    ]
  }
}
```

Every row has `id` and `score`. Generation rows have `rendered_sha256`, the hash of the exact prompt text the model received after its chat template. Other fields depend on the task: `confidence` for multiple choice, `followed` and `unsupported` for IFEval, `passed` and `error` for HumanEval, `refused` for refusal tasks.

## Proof

| Field | Type | Meaning |
| --- | --- | --- |
| `algorithms` | object | Names of the canonical JSON, hash, Merkle and audit id rules |
| `audit_id` | string | Same as the top level `audit_id` |
| `suite_root` | string | Merkle root of the suite items |
| `results_root` | string | Merkle root of every per item result |
| `statement_sha256` | string | Hash of audit id, results root, metrics, verdict, comparability and weights diff |

See [Fingerprints and proof](../concepts/proof.md) for how each is computed.

## Parsing safely

```python
import json

report = json.load(open("audit/report.json"))
if report["schema_version"] != "0.3":
    raise RuntimeError(f"unsupported schema {report['schema_version']}")
```

Reports from 0.2 still verify with this version. Reports from 0.1 have no `audit_id`, `manifest`, `fingerprints` or `proof`, and cannot be verified.
