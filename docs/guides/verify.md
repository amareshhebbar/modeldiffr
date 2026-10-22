---
title: Verify a report
description: Check that a report was not edited and refers to the exact models it names.
---

# Verify a report

Check that a report was not edited and refers to the exact models it names.

## Offline check

No GPU, no network, no model download. Takes under a second.

```bash
pip install "modeldiffr[proof]"
modeldiffr verify report.json
```

```text
audit id mdr1:71e153dc730bb9ec20b7159dc8845afab76de27ddf94b99cada26c713aa3170d
PASS  schema                     valid against report schema 0.2
PASS  audit_id                   mdr1:71e153dc730bb9ec20b7159dc8845afab76de27ddf94b99cada26c713aa3170d
PASS  manifest_consistency       settings and fingerprints match the manifest
PASS  suite                      matches the built in suite
PASS  results_root               sha256:639596b69b14c62253b7ac4e7837a6b401d61493885ea4094075a2b1ea860714
PASS  metrics                    3 metrics recomputed from the items
PASS  verdict                    no change
PASS  base_weights_leaves        21 tensors
PASS  derivative_weights_leaves  21 tensors
PASS  weights_diff               1 of 21 shared tensors changed
PASS  statement                  claims match the statement hash

verified
```

The `proof` extra installs `jsonschema` for the full schema check. Without it, `verify` still runs every other check and only confirms the required fields exist.

If anything was edited, the matching check fails and the command exits with code `4`:

```text
FAIL  results_root               items were changed
FAIL  metrics                    capability_accuracy.delta is 0.0, items give -0.0417
```

## Check against the real model files

`--models` also reads both models and confirms their weights hash to the recorded roots. Hub models are downloaded at the exact commit recorded in the report. Local paths are read in place.

```bash
modeldiffr verify report.json --models
```

```text
PASS  base_model_files           weights match the report
PASS  derivative_model_files     weights match the report
```

This needs `huggingface_hub` for Hub models, which the `hf` extra installs. It reads every weight file once, so it takes about as long as copying the model from disk.

## In CI

Verify every report that lands in your repository:

```yaml
- run: pip install "modeldiffr[proof]"
- run: |
    for f in audits/*/report.json; do
      modeldiffr verify "$f" || exit 1
    done
```

`--json` prints a machine readable result:

```bash
modeldiffr verify report.json --json | jq '.ok, [.checks[] | select(.status == "fail")]'
```

## From Python

```python
from modeldiffr.proof.verify import verify_file

result = verify_file("report.json", check_models=False)
if not result["ok"]:
    for check in result["checks"]:
        if check["status"] == "fail":
            print(check["name"], check["detail"])
```

## Compare two audits

Two reports with the same `audit_id` audited the same pair with the same suite and settings. If their `results_root` differs, the runs produced different per item results, usually because of different hardware. The `environment` field says where each ran.

See [Fingerprints and proof](../concepts/proof.md) for what each check means and what verification does not prove.
