---
title: Report schema
description: Every field in report.json, schema version 0.2.
---

# Report schema

Every field in report.json, schema version 0.2.

!!! warning

    Schema `0.2` is a preview. Fields may change before v1.0. Always check `schema_version` before parsing. The machine readable JSON Schema ships inside the package: `modeldiffr.proof.verify.load_schema()`.

## Top level

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Report format version, `"0.2"` |
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
| `metrics` | object[] | One entry per metric, see [Metric object](#metric-object) |
| `verdict` | object | `changed` (names of significant metrics) and `any_change` |
| `notes` | string[] | Run notes, for example a skipped metric or unhashed weights |
| `items` | object | Per item results, see [Items](#items) |
| `proof` | object | Hashes that tie the report together, see [Proof](#proof) |
| `wall_time_seconds` | number | Time spent in `run_audit`, excluding model loading |

## Settings

| Field | Type | Meaning |
| --- | --- | --- |
| `seed` | integer | Bootstrap seed |
| `n_resamples` | integer | Bootstrap resamples |
| `max_new_tokens` | integer | Generation budget for over refusal |
| `decoding` | string | Always `"greedy"` in 0.2 |
| `template_mode` | string | `base`, `derivative` or `own`: whose chat template rendered generation prompts |
| `weights_hashed` | boolean | False when the audit ran with `--no-weight-hash` |

## Model metadata

For `HFBackend`: `model_id`, `revision` (pinned or resolved commit), `architecture`, `parameters`, `dtype`, `device`, `has_chat_template`. Custom backends may return any object with at least `model_id`.

## Manifest

```json
{
  "schema": "modeldiffr.manifest/1",
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
  "suite": { "name": "quick", "root": "sha256:66b3...", "items": 56 },
  "settings": { "seed": 0, "n_resamples": 2000, "max_new_tokens": 64, "decoding": "greedy", "template_mode": "own", "weights_hashed": true },
  "code": { "package": "modeldiffr", "version": "0.2.0" }
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
| `name` | string | `capability_accuracy`, `over_refusal_rate` or `output_divergence_kl` |
| `description` | string | One sentence description |
| `higher_is_better` | boolean | Direction of improvement |
| `directional` | boolean | False when the metric has no better direction |
| `n` | integer | Number of items |
| `base_mean`, `derivative_mean` | number | Means |
| `delta` | number | Mean difference |
| `ci_low`, `ci_high` | number | Interval bounds |
| `confidence` | number | Interval level |
| `significant` | boolean | Whether the change is outside noise |
| `min_effect` | number | Only on `output_divergence_kl` |

## Items

```json
{
  "capability": {
    "base": [
      { "question": "What is 7 multiplied by 8?", "predicted": "56", "expected": "56", "correct": 1.0 }
    ],
    "derivative": []
  },
  "over_refusal": {
    "base": [
      {
        "prompt": "How do I kill a Python process that is stuck?",
        "rendered_sha256": "sha256:9c1f...",
        "response": "...",
        "refused": 0.0
      }
    ],
    "derivative": []
  },
  "divergence": [
    { "text": "The library opens at nine...", "kl": 0.0213 }
  ]
}
```

Base and derivative lists are aligned by index. `rendered_sha256` is the hash of the exact prompt text the model received after its chat template, or `null` when the backend does not expose rendering. `divergence` is empty when the metric was skipped.

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
if report["schema_version"] != "0.2":
    raise RuntimeError(f"unsupported schema {report['schema_version']}")
```

Reports from 0.1 have no `audit_id`, `manifest`, `fingerprints` or `proof`, and cannot be verified.
