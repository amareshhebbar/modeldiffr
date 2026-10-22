---
title: Schemas and compatibility
description: Every file format Modeldiffr writes, which parts are stable, and the promise that applies from 1.0.
---

# Schemas and compatibility

Every file format Modeldiffr writes, which parts are stable, and the promise that applies from 1.0.

## Formats

| File | Schema id | JSON Schema in the package | Id prefix |
| --- | --- | --- | --- |
| `report.json` | `schema_version` `0.3` | `modeldiffr/schema/report.schema.json` | `mdr1:` |
| `report.json` from 0.2 | `schema_version` `0.2` | `modeldiffr/schema/report-0.2.schema.json` | `mdr1:` |
| Attestation predicate | `https://modeldiffr.dev/attestation/audit/v1` | `modeldiffr/schema/audit-predicate-v1.schema.json` | none |
| `features.json` | `modeldiffr.features/1` | `modeldiffr/schema/features.schema.json` | `mdrf1:` |
| `causal.json` | `modeldiffr.causal/1` | `modeldiffr/schema/causal.schema.json` | `mdrc1:` |
| `scan.json` | `modeldiffr.scan/1` | `modeldiffr/schema/scan.schema.json` | `mdrs1:` |
| `*.commitment.json` | `modeldiffr.commitment/1` | none | none |
| `index.json` from batch | `modeldiffr.batch/1` | none | none |
| `registry.json` | `modeldiffr.registry/1` | none | none |
| `study.json` | `modeldiffr.study/1` | none | none |

`modeldiffr verify` validates reports, features, causal and scan files against their schema whenever `jsonschema` is installed (`pip install "modeldiffr[proof]"`).

## Report schema 1.0 candidate

Report schema 0.3 is the candidate for 1.0. It will become 1.0 unchanged unless the published audits of Phase 8 show a field that cannot be kept. These parts are frozen now:

* The manifest: `schema`, `base`, `derivative`, `suite`, `settings`, `code`, and the model entry fields `model_id`, `revision`, `commit`, `weights_root`, `weights_algorithm`, `tokenizer_vocab`, `tokenizer_json`, `chat_template`.
* The audit id: `mdr1:` plus SHA 256 of the RFC 8785 canonical JSON of the manifest.
* `items` and the results root: RFC 6962 Merkle tree with leaves `{"task", "side", "index", "row"}` over tasks in sorted order and sides `base`, `derivative`, `pair`.
* The statement hash: SHA 256 of the canonical JSON of `audit_id`, `results_root`, `metrics`, `verdict`, `comparability` and `weights_diff`.
* Every metric's `name`, `n`, `base_mean`, `derivative_mean`, `delta`, `ci_low`, `ci_high`, `p_value`, `significant`, `significant_raw`, `negligible` and `spec`.
* `verdict` with `changed`, `negligible` and `any_change`.
* The weight fingerprint algorithm `modeldiffr.weights/1`.

## The promise from 1.0

1. **Reports keep verifying.** Every report written by any 1.x version verifies with every later 1.x version, offline, with the same result. Reports from 0.2 and 0.3 keep verifying too.
2. **Ids never change meaning.** An audit id, features id, causal id or scan id computed by one version is computed identically by every later version for the same inputs.
3. **Additive changes only within 1.x.** New optional fields may appear. Existing fields are not removed, renamed or given a new meaning.
4. **Breaking changes need a new major schema** with a new id prefix (`mdr2:`), and the old schema stays verifiable for at least two years.
5. **Deprecations are announced** in the changelog at least one minor release before anything optional stops being written.
6. **The attestation predicate** `audit/v1` follows the same rules. A breaking change gets `audit/v2`.

## Version numbers

The package follows Semantic Versioning. Until 1.0, minor releases may change formats, and the changelog says how. Every format change so far has kept older reports verifiable.
