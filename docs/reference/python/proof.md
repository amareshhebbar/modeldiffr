---
title: Proof and fingerprint API
description: Hash models, build audit ids, and verify reports from Python.
---

# Proof and fingerprint API

Hash models, build audit ids, and verify reports from Python.

## Fingerprints

```python
from modeldiffr.fingerprint import (
    diff_weights,
    resolve_model_dir,
    tokenizer_fingerprint,
    weights_fingerprint,
)

base_dir, base_commit = resolve_model_dir("Qwen/Qwen2.5-0.5B-Instruct")
tuned_dir, _ = resolve_model_dir("./checkpoints/step_4000")

a = weights_fingerprint(base_dir)
b = weights_fingerprint(tuned_dir)
print(a.root, a.tensors, a.bytes, a.format)

diff = diff_weights(a.leaves, b.leaves)
print(diff["changed_count"], diff["changed"][:10])
```

#### `weights_fingerprint(model_dir)`

Returns a `WeightsFingerprint` with `root`, `tensors`, `bytes`, `format`, `leaves` (tensor name to leaf hash) and `algorithm`. `to_dict(include_leaves=True)` gives the report form. Raises `UnsupportedWeightsError` when no supported weight files are found.

#### `diff_weights(base_leaves, derivative_leaves, limit=200)`

Returns `identical`, `shared`, `changed_count`, `added_count`, `removed_count`, `unchanged_count`, and up to `limit` names in `changed`, `added` and `removed`, with `truncated` set when lists were cut.

#### `tokenizer_fingerprint(tokenizer, model_dir=None)`

Takes any tokenizer with `get_vocab()` and returns `vocab`, `vocab_size`, `special_tokens`, `chat_template` and `tokenizer_json` hashes.

#### `resolve_model_dir(model, revision=None)`

Returns `(path, commit)`. Local directories are used in place with `commit` set to `None`.

## Canonical JSON and Merkle trees

```python
from modeldiffr.proof.canonical import canonical_json, object_hash
from modeldiffr.proof.merkle import inclusion_proof, leaf_hash, merkle_root, verify_inclusion

canonical_json({"b": 1, "a": [1.0, "x"]})
object_hash({"b": 1})

leaves = [leaf_hash(x.encode()) for x in ["a", "b", "c"]]
root = merkle_root(leaves)
proof = inclusion_proof(leaves, 1)
assert verify_inclusion(leaves[1], 1, len(leaves), proof, root)
```

`canonical_json` implements RFC 8785 and raises `CanonicalizationError` for NaN, infinity, non string keys and integers beyond 2 to the power 53. The Merkle tree follows RFC 6962, with `0x00` and `0x01` prefixes for leaves and nodes.

## Manifest and audit id

```python
from modeldiffr.proof.manifest import audit_id, build_manifest, results_root, suite_root

suite_root(suite)
results_root(result["items"])
audit_id(result["manifest"])
```

`run_audit` builds all of these for you. Use them directly to precompute an audit id before running, or to check another tool's output.

## Verification

```python
from modeldiffr.proof.verify import load_schema, verify_file, verify_report

result = verify_file("report.json", check_models=True, progress=print)
result["ok"]
result["checks"]
```

`load_schema()` returns the bundled JSON Schema for reports, the same file used by the `schema` check.
