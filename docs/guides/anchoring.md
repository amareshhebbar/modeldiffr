---
title: Timestamp and anchor
description: Prove when an audit existed with OpenTimestamps or the Ethereum Attestation Service, and commit to private suites.
---

# Timestamp and anchor

Prove when an audit existed with OpenTimestamps or the Ethereum Attestation Service, and commit to private suites.

```bash
pip install "modeldiffr[anchor]"
```

Anchors are optional. Only `statement_sha256` is published, which reveals nothing about the models or prompts.

## OpenTimestamps on Bitcoin

```bash
modeldiffr anchor ots audit/report.json
```

```text
wrote audit/statement.sha256
the Bitcoin attestation completes in a few hours: modeldiffr anchor upgrade REPORT
```

This writes `statement.sha256` (the hash as text) and `statement.sha256.ots` (the pending proof). Public calendars batch many submissions into one Bitcoin transaction, so it is free. A few hours later:

```bash
modeldiffr anchor upgrade audit/report.json
modeldiffr verify audit/report.json
```

```text
PASS  opentimestamps             anchored in a Bitcoin block
```

Before the upgrade the check passes with `submitted to calendars, waiting for a Bitcoin block`.

## Ethereum Attestation Service

One attestation per audit on an L2, readable by anyone and by contracts.

1. Register the schema once on [easscan.org](https://base.easscan.org/schema/create):

    ```text
    bytes32 auditId,bytes32 resultsRoot,bytes32 statementSha256,string verdict
    ```

    Note the schema UID it returns.

2. Fund an account with a little ETH on the chain and export its key:

    ```bash
    export MODELDIFFR_ETH_KEY=0x...
    ```

3. Attest:

    ```bash
    modeldiffr anchor eas audit/report.json \
      --schema 0xSCHEMA_UID \
      --rpc https://mainnet.base.org
    ```

    ```text
    attestation 0x5c2e... in transaction 0x8a91...
    ```

The record is appended to `anchors.json`. Anyone can check it:

```bash
modeldiffr verify audit/report.json --rpc https://mainnet.base.org
```

```text
PASS  eas                        attested on chain 8453 by 0x3F1a...
```

The check reads the attestation from the EAS contract at `0x4200000000000000000000000000000000000021`, fails if it was revoked, and compares all three hashes with the report.

| Chain | Chain id | RPC example |
| --- | --- | --- |
| Base | 8453 | `https://mainnet.base.org` |
| Base Sepolia | 84532 | `https://sepolia.base.org` |
| Optimism | 10 | `https://mainnet.optimism.io` |

!!! warning

    The private key never leaves your machine, and Modeldiffr never writes it to disk. Use an account that holds only enough for fees.

## Commit and reveal private suites

Keep a holdout suite private while proving it existed before a model was trained.

```bash
modeldiffr commit holdout.jsonl
```

```text
root sha256:4be1... over 500 items, wrote holdout.jsonl.commitment.json
publish the commitment now and keep the file private until you reveal it
```

Publish the commitment (and timestamp it with `ots stamp holdout.jsonl.commitment.json`). Later, publish the file and anyone can check it:

```bash
modeldiffr reveal holdout.jsonl --commitment holdout.jsonl.commitment.json
```

```text
PASS 500 items match the commitment made at 2026-10-22T10:31:02+00:00
```

Each row is hashed as canonical JSON with its index, so reordering keys does not change the root and changing any value or the order of rows does. `reveal` exits with `4` on a mismatch.
