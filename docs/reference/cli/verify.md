---
title: modeldiffr verify
description: Check a report for consistency and, optionally, against the real model files.
---

# modeldiffr verify

Check a report for consistency and, optionally, against the real model files.

```text
usage: modeldiffr verify [-h] [--models] [--json] report
```

## Arguments

#### `report`

*string*, required

Path to a `report.json` written by `modeldiffr audit`.

## Options

#### `--models`

*flag*

Also hash both models' weights and compare them with the roots in the report. Hub models are fetched at the recorded commit. Needs the `hf` extra.

#### `--json`

*flag*

Print the result as JSON instead of a table:

```json
{
  "ok": true,
  "audit_id": "mdr1:71e1...",
  "checks": [
    {"name": "schema", "status": "pass", "detail": "valid against report schema 0.2"}
  ]
}
```

Each check has `status` `pass`, `fail` or `skip`. A check is skipped when the report has nothing to check, for example a custom suite whose items are not bundled, or a backend that does not report weight hashes.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every check passed or was skipped |
| `2` | The file could not be read or is not JSON |
| `4` | At least one check failed |

See [Verify a report](../../guides/verify.md) for examples and [Fingerprints and proof](../../concepts/proof.md) for what each check means.
