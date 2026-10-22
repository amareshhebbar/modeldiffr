---
title: run_audit
description: Run a full audit and return the result dict.
---

# run_audit

Run a full audit and return the result dict.

```python
from modeldiffr import run_audit

result = run_audit(base, derivative, suite, seed=0, n_resamples=2000, progress=print)
```

## Signature

```python
def run_audit(
    base: Backend,
    derivative: Backend,
    suite: Suite,
    seed: int = 0,
    n_resamples: int = 2000,
    progress: Callable[[str], None] = _noop,
    template: str = "auto",
    hash_weights: bool = True,
) -> dict
```

## Parameters

#### `base`

*Backend*, required

The reference model. Any object implementing the [Backend protocol](backend_protocol.md), usually an [`HFBackend`](hf_backend.md).

#### `derivative`

*Backend*, required

The model under audit.

#### `suite`

*Suite*, required

Items to evaluate. Get a built in one with `get_suite("quick")`.

#### `seed`

*int*, default `0`

Bootstrap seed.

#### `n_resamples`

*int*, default `2000`

Bootstrap resamples per metric.

#### `progress`

*Callable[[str], None]*

Called with a short message at each stage. Defaults to a no op.

#### `template`

*str*, default `"auto"`

`auto`, `base`, `derivative` or `own`. Which chat template renders generation prompts. See [comparable prompts](../../concepts/proof.md#comparable-prompts).

#### `hash_weights`

*bool*, default `True`

Fingerprint both models' weights. Set to `False` to skip hashing; the report is then not tied to exact weights.

## Returns

A dict matching the [report schema](../report_schema.md). Key fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `audit_id` | str | `mdr1:` id computed from the manifest before anything runs |
| `metrics` | list[dict] | One entry per metric with means, delta, interval and `significant` |
| `verdict` | dict | `changed`, names of significant metrics, and `any_change` |
| `comparability` | dict | Template mode and issues found before running |
| `weights_diff` | dict or None | Which tensors changed, were added or removed |
| `proof` | dict | Suite root, results root and statement hash |
| `notes` | list[str] | Run notes, such as a skipped divergence metric |
| `items` | dict | Per item results for both models |

## Raises

`ComparabilityError` from `modeldiffr.checks` when the pair cannot be compared fairly, for example a shared template forced across different tokenizers. `exc.issues` lists the reasons.

## Execution order

1. Fingerprint both models, if the backends support it.
2. Check comparability and choose the template mode.
3. Build the manifest and the audit id.
4. Capability scoring on base, then derivative.
5. Over refusal generation on base, then derivative, with one shared template when templates differ.
6. Output divergence, only when `base.vocab_signature() == derivative.vocab_signature()`.
7. Statistics, weights diff and proof hashes.

## Constants

| Name | Value | Meaning |
| --- | --- | --- |
| `modeldiffr.audit.SCHEMA_VERSION` | `"0.2"` | Report schema version |
| `modeldiffr.audit.KL_TOLERANCE` | `1e-3` | Minimum KL lower bound to count as changed |
