---
title: controls, batch, registry
description: Commands for planted regressions, many audits at once and the public registry.
---

# controls, batch, registry

Commands for planted regressions, many audits at once and the public registry.

## controls make

```text
usage: modeldiffr controls make [--out OUT] [--kind {identity,noise,scale,zero,prune}]
                                [--strength STRENGTH] [--match MATCH] [--seed SEED]
                                [--revision REVISION] base
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--out` | required | Empty or new folder for the control model |
| `--kind` | `noise` | Perturbation, see [Positive controls](../../guides/controls.md) |
| `--strength` | `0.05` | Noise scale, factor or pruned share |
| `--match` | attention and MLP projections | Regular expression on tensor names |
| `--seed` | `0` | Seed for noise |
| `--revision` | latest | Base model revision |

Needs the `hf` extra and safetensors weights.

## batch

```text
usage: modeldiffr batch [--out OUT] [--only ONLY] [--rerun] [--dry-run] spec
```

See [Batch audits](../../guides/batch.md). Exits with `0` when every audit finished, `5` when any failed.

## registry build

```text
usage: modeldiffr registry build [--out OUT] [--title TITLE] [--key NAME=PATH]
                                 [--allow-failed] [--base-url URL] paths [paths ...]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--out` | `registry_site` | Output folder, replaced on every build |
| `--title` | `Modeldiffr audit registry` | Site title |
| `--key` | none | Publisher public key; repeat for several publishers |
| `--allow-failed` | off | List reports that fail verification |

Exits with `4` when any report was skipped. See [Public registry](../../guides/registry.md).
