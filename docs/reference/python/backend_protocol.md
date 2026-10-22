---
title: Backend protocol
description: The interface every model backend implements.
---

# Backend protocol

The interface every model backend implements.

```python
from modeldiffr.backend import Backend
```

`Backend` is a `typing.Protocol`. Any object with these members works with `run_audit`. No inheritance is required.

## Members

- **`name`** *str*: Human readable model identifier.

- **`metadata()`** *dict*: Model details written into the report under `base` or `derivative`. Must contain `model_id`. Any other JSON serializable keys are shown in the HTML model card.

- **`choice_logprob(prompt, continuation)`** *float*: Summed log probability of `continuation` given `prompt`, counting continuation tokens only. Called once per choice per capability item.

- **`generate(prompt, max_new_tokens)`** *str*: Greedy completion for a user prompt, returning only the new text. Called once per benign prompt.

- **`vocab_signature()`** *str*: A string that is equal for two backends if and only if their tokenizers are identical. Divergence runs only when signatures match.

- **`divergence_to(other, text)`** *float*: Non negative mean per token KL from `self` to `other` on `text`. Called on the base backend with the derivative as `other`.

## Optional members for proof

Backends that add these get fingerprints, a tensor level weights diff and shared template rendering. Without them, audits still run and verify, and the report records a `missing_fingerprint` warning. `HFBackend` implements all three.

- **`fingerprint(weights=True)`** *dict*: `{"commit": str | None, "tokenizer": dict, "weights": dict | None}`. Build `tokenizer` with `modeldiffr.fingerprint.tokenizer_fingerprint` and `weights` with `weights_fingerprint(path).to_dict()`. Raise `UnsupportedWeightsError` when the weights cannot be hashed; Modeldiffr then retries with `weights=False`.

- **`render_chat(prompt)`** *str*: The full prompt text after this model's chat template.

- **`generate_raw(text, max_new_tokens)`** *str*: Greedy completion for already rendered text. Used when both models must receive the same rendered prompt.

## Call counts for the quick suite

| Method | Calls per model |
| --- | --- |
| `choice_logprob` | 96 (24 items, 4 choices each) |
| `generate` | 20 |
| `vocab_signature` | 1 |
| `divergence_to` | 12, on the base backend only |
| `metadata` | 1 |

See [Custom backends](../../guides/custom_backend.md) for a worked example.
