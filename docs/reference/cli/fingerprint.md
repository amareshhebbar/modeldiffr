---
title: modeldiffr fingerprint
description: Print content hashes for one model without running an audit.
---

# modeldiffr fingerprint

Print content hashes for one model without running an audit.

```text
usage: modeldiffr fingerprint [-h] [--revision REVISION] [--leaves] [--json] model
```

Use it to pin a model in a model card, to check that two uploads are the same weights, or to see which tensors a fine tune touched.

```bash
modeldiffr fingerprint ./checkpoints/step_4000
```

```text
model          ./checkpoints/step_4000
weights root   sha256:194b404d99de3d507664c452555a641147f697491e14ee29fd2632ac8089b8b9
tensors        21 (188,800 bytes, safetensors)
vocab          sha256:395b8af95f1f4d7b0d9091287c0b2073e24f2860bf71f8e77654a904c854c306 (415 tokens)
tokenizer.json sha256:db3150f82f955f62d7a95aa1768b5366cb4f83b0588ca232d35a363772f8456f
chat template  sha256:85ed6a3dbe40efa25c2d790b07f9739515f9ef46126d92db2c3c886c42fa169f
```

## Arguments

#### `model`

*string*, required

A Hugging Face model id or a local directory. Hub models are downloaded once into the normal Hugging Face cache.

## Options

#### `--revision`

*string*

Branch, tag or commit for Hub models. The resolved commit is printed.

#### `--leaves`

*flag*

Also print the hash of every tensor, one per line, sorted by name. Diff two of these outputs to see which tensors changed.

#### `--json`

*flag*

Print everything as JSON, in the same shape as `fingerprints.base` in a report.

## Supported formats

| Format | Supported |
| --- | --- |
| safetensors, single file or sharded | Yes, read directly, every dtype |
| PyTorch `.bin`, `.pt`, `.pth` | Yes, needs `torch`; gives the same root as the same weights in safetensors |
| GGUF | Not yet, arrives with the llama.cpp backend in Phase 2 |

The tokenizer hashes need `transformers`. Without it, only the weights are fingerprinted.
