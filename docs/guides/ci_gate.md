---
title: CI gate
description: Block a checkpoint that changes significantly before it ships.
---

# CI gate

Block a checkpoint that changes significantly before it ships.

`--fail-on-change` makes `modeldiffr audit` exit with code `1` when any metric changes significantly. Use it to stop a training run, a quantization job, or a merge from shipping a silent regression.

## GitHub Actions

```yaml .github/workflows/model_audit.yml
name: Model audit

on:
  pull_request:
    paths:
      - "checkpoints/**"

jobs:
  audit:
    runs-on: [self-hosted, gpu]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install
        run: pip install "modeldiffr[hf]"

      - name: Audit the new checkpoint
        run: |
          modeldiffr audit org/base_model ./checkpoints/candidate \
            --base-revision ${{ vars.BASE_REVISION }} \
            --seed 0 \
            --fail-on-change \
            --out audit

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: modeldiffr_audit
          path: audit/
```

!!! tip

    `if: always()` uploads the report even when the gate fails, which is exactly when you need to read it.

## GitLab CI

```yaml .gitlab-ci.yml
model_audit:
  image: python:3.11
  tags: [gpu]
  script:
    - pip install "modeldiffr[hf]"
    - modeldiffr audit org/base_model ./checkpoints/candidate --fail-on-change --out audit
  artifacts:
    when: always
    paths:
      - audit/
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Audit completed. With `--fail-on-change`, no metric changed. |
| `1` | `--fail-on-change` was set and at least one metric changed significantly. |
| `2` | Missing dependency. Install `modeldiffr[hf]`. |

## Gating on one metric only

`--fail-on-change` fails on **any** significant change, including `output_divergence_kl`, which almost always moves after a fine tune. For a fine tune you expect to change outputs, gate on regressions only by reading the JSON:

```python scripts/gate.py
import json
import sys

report = json.load(open(sys.argv[1]))
regressions = [
    m["name"]
    for m in report["metrics"]
    if m["significant"]
    and m["directional"]
    and (m["delta"] > 0) != m["higher_is_better"]
]
if regressions:
    print("regressed:", ", ".join(regressions))
    sys.exit(1)
```

```bash
modeldiffr audit org/base_model ./checkpoints/candidate --out audit
python scripts/gate.py audit/report.json
```

!!! note

    For quantized builds and lossless conversions, the plain `--fail-on-change` gate is usually what you want: any measurable movement is worth a look.
