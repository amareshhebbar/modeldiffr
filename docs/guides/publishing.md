---
title: Publish an audit
description: Upload reports to the Hugging Face Hub, add a model card badge, export an AI bill of materials and gate checkpoints with the GitHub Action.
---

# Publish an audit

Upload reports to the Hugging Face Hub, add a model card badge, export an AI bill of materials and gate checkpoints with the GitHub Action.

## Hugging Face Hub

Audit straight from Hub URLs, including a branch or commit:

```bash
modeldiffr audit https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct \
  https://huggingface.co/org/qwen-ft/tree/v2 --suite lite --out audit
```

Upload the report folder to the derivative's repository:

```bash
huggingface-cli login
modeldiffr hub push audit --repo org/qwen-ft
```

```text
uploaded report.json, report.html, report.dsse.json to https://huggingface.co/org/qwen-ft/blob/main/modeldiffr/71e1c0a4b2d39f10/report.html
add this to the model card:
[![Modeldiffr audit](https://img.shields.io/badge/modeldiffr-1%20changed-b3261e)](https://huggingface.co/...)
```

Files go under `modeldiffr/<first 16 hex of the audit id>/`, so several audits of one model live side by side. Only report, signature, timestamp and bill of materials files are uploaded; nothing else in the folder is.

Print the badge for any hosted report:

```bash
modeldiffr badge audit/report.json --url https://example.org/audits/qwen-ft
```

## AI bill of materials

```bash
modeldiffr bom audit/report.json --format cyclonedx --out audit/bom.cdx.json
modeldiffr bom audit/report.json --format spdx --out audit/bom.spdx.json
```

| Format | Version | Contents |
| --- | --- | --- |
| CycloneDX | 1.6 | Both models as `machine-learning-model` components with weight hashes, the derivative depending on the base, every metric as a property |
| SPDX | 3.0.1 | Both models as `ai_AIPackage` elements with `verifiedUsing` hashes and a relationship from derivative to base |

Both are deterministic: the same report always gives the same document.

## GitHub Action

The repository ships a composite action that audits, gates, signs with Sigstore, writes a bill of materials and uploads everything as an artifact.

```yaml .github/workflows/audit.yml
name: Model audit
on:
  pull_request:
    paths: ["checkpoints/**"]

permissions:
  id-token: write
  contents: read

jobs:
  audit:
    runs-on: [self-hosted, gpu]
    steps:
      - uses: actions/checkout@v4
      - id: mdr
        uses: amareshhebbar/modeldiffr@v0.4.0
        with:
          base: org/base_model
          derivative: ./checkpoints/candidate
          suite: lite
          fail-on-change: "true"
      - run: echo "audit ${{ steps.mdr.outputs.audit-id }} changed ${{ steps.mdr.outputs.changed }}"
```

| Input | Default | Meaning |
| --- | --- | --- |
| `base`, `derivative` | required | Model ids, paths or Hub URLs |
| `suite` | `quick` | Suite name |
| `tasks`, `limit` | empty | Same as the CLI options |
| `fail-on-change` | `true` | Fail the job when any metric changes |
| `sign` | `true` | Sign with Sigstore; needs `id-token: write` |
| `extra-args` | empty | Passed to `modeldiffr audit` |
| `version` | latest | Modeldiffr version to install |
| `out` | `modeldiffr_report` | Report folder, uploaded as the `modeldiffr-audit` artifact |

Outputs are `audit-id` and `changed`. The report is uploaded and signed even when the gate fails, which is when you need it. Verify a signature from the action with:

```bash
modeldiffr verify report.json \
  --identity "https://github.com/OWNER/REPO/.github/workflows/audit.yml@refs/pull/12/merge" \
  --issuer https://token.actions.githubusercontent.com
```
