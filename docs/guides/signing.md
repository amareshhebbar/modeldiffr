---
title: Sign and verify
description: Sign reports with an Ed25519 key or Sigstore, and check signatures on reports and model repositories.
---

# Sign and verify

Sign reports with an Ed25519 key or Sigstore, and check signatures on reports and model repositories.

```bash
pip install "modeldiffr[sign]"
```

## With a key

Good for offline machines, air gapped clusters and organisations that already manage keys.

```bash
modeldiffr keygen --out keys --name acme
```

```text
private key keys/acme.key  (keep it secret)
public key  keys/acme.pub   (publish it so others can verify)
```

The private key is written with mode `0600`. Sign an existing report:

```bash
modeldiffr sign audit/report.json --key keys/acme.key
```

```text
wrote audit/report.dsse.json
```

Or sign as part of the audit:

```bash
modeldiffr audit org/base org/derivative --suite lite --out audit --sign-key keys/acme.key
```

Anyone with the public key checks it:

```bash
modeldiffr verify audit/report.json --key acme.pub
```

```text
PASS  signature                  signed with acme.pub
```

## With Sigstore

No keys to manage. The signature is tied to an identity such as a GitHub Actions workflow or an email address, and recorded in the public Rekor log.

=== "GitHub Actions"

    ```yaml
    permissions:
      id-token: write
      contents: read
    steps:
      - run: modeldiffr sign audit/report.json --sigstore
    ```
    The workflow's OpenID Connect token is detected automatically.

=== "Laptop"

    ```bash
    modeldiffr sign audit/report.json --sigstore
    ```
    A browser window opens to sign in with GitHub, Google or Microsoft.

=== "Explicit token"

    ```bash
    modeldiffr sign audit/report.json --sigstore --identity-token "$OIDC_TOKEN"
    ```

Verify with the identity you expect:

```bash
modeldiffr verify audit/report.json \
  --identity https://github.com/acme/models/.github/workflows/audit.yml@refs/heads/main \
  --issuer https://token.actions.githubusercontent.com
```

```text
PASS  sigstore                   signed by https://github.com/acme/models/..., logged in Rekor
```

Use `--staging` on both commands to try the Sigstore staging instance.

## Signatures on model repositories

Model publishers can sign their files with [OpenSSF model signing](https://github.com/sigstore/model-transparency), which writes `model.sig` next to the weights. `verify --models` downloads it with the weights and checks it when the `model-signing` package is installed:

```bash
pip install model-signing
modeldiffr verify audit/report.json --models \
  --identity publisher@example.org --issuer https://github.com/login/oauth
```

```text
PASS  base_model_files           weights match the report
PASS  base_model_signature       OpenSSF model signature verified
```

## What verify reports

Every attestation found next to `report.json` adds a check. Missing inputs skip a check rather than fail it, so unsigned reports still verify.

| Check | Reads | Needs |
| --- | --- | --- |
| `signature` | `report.dsse.json` | `--key` |
| `sigstore` | `report.sigstore.json` | `--identity` and `--issuer` |
| `opentimestamps` | `statement.sha256.ots` | the `ots` client |
| `eas` | `anchors.json` | `--rpc` |
| `*_model_signature` | `model.sig` in the model | `--models`, `model-signing` |

Next: [Timestamp and anchor](anchoring.md).
