---
title: Signing and publishing commands
description: keygen, sign, anchor, commit, reveal, bom, hub push and badge.
---

# Signing and publishing commands

keygen, sign, anchor, commit, reveal, bom, hub push and badge.

## keygen

```text
usage: modeldiffr keygen [--out DIR] [--name NAME]
```

Writes `NAME.key` (PKCS 8 PEM, mode `0600`) and `NAME.pub` (SubjectPublicKeyInfo PEM) for Ed25519. Defaults: `--out keys`, `--name modeldiffr`. Refuses to overwrite existing files. Needs the `sign` extra.

## sign

```text
usage: modeldiffr sign [--key KEY] [--sigstore] [--staging] [--identity-token TOKEN] report
```

| Option | Meaning |
| --- | --- |
| `--key` | Ed25519 private key; writes `report.dsse.json` |
| `--sigstore` | Keyless signing; writes `report.sigstore.json` |
| `--staging` | Use the Sigstore staging instance |
| `--identity-token` | OpenID Connect token; otherwise detected in CI or obtained in a browser |

Both may be given at once. At least one is required, otherwise the command exits with `2`. `audit` accepts `--sign-key` and `--sigstore` to sign right after writing the report.

## anchor

```text
usage: modeldiffr anchor ots REPORT
       modeldiffr anchor upgrade REPORT
       modeldiffr anchor eas REPORT --schema UID --rpc URL [--key-env NAME]
```

| Subcommand | Writes |
| --- | --- |
| `ots` | `statement.sha256` and `statement.sha256.ots` next to the report |
| `upgrade` | Completes the `.ots` proof in place once Bitcoin has confirmed it |
| `eas` | Appends `{chain_id, contract, schema, tx, uid, attester}` to `anchors.json` |

`eas` reads the private key from the environment variable named by `--key-env` (default `MODELDIFFR_ETH_KEY`). Needs the `anchor` extra.

## commit and reveal

```text
usage: modeldiffr commit FILE [--out PATH]
       modeldiffr reveal FILE --commitment PATH
```

`commit` writes `FILE.commitment.json`:

```json
{
  "schema": "modeldiffr.commitment/1",
  "file": "holdout.jsonl",
  "root": "sha256:4be1...",
  "items": 500,
  "created_at": "2026-10-22T10:31:02+00:00"
}
```

`reveal` prints `PASS` and exits `0`, or prints `FAIL` and exits `4`.

## bom

```text
usage: modeldiffr bom [--format {cyclonedx,spdx}] [--out PATH] report
```

Prints to standard output when `--out` is not given.

## hub push

```text
usage: modeldiffr hub push REPORT_DIR --repo REPO_ID
```

Uploads known report files to `modeldiffr/<short id>/` in the repository and prints a badge. Uses the token from `huggingface-cli login` or `HF_TOKEN`.

## badge

```text
usage: modeldiffr badge --url URL report
```

Prints a Markdown badge: green `no significant change`, or red `N changed`.

## verify options for attestations

| Option | Meaning |
| --- | --- |
| `--key` | Public key for `report.dsse.json` |
| `--identity`, `--issuer` | Expected Sigstore signer and OpenID Connect issuer, also used for `model.sig` |
| `--staging` | Sigstore staging trust root |
| `--rpc` | JSON RPC endpoint used to read EAS attestations |

See [Sign and verify](../../guides/signing.md) and [Timestamp and anchor](../../guides/anchoring.md).
