---
title: Public registry
description: Publish audits as a static site where every visitor can recompute the hashes and check the signature in the browser.
---

# Public registry

Publish audits as a static site where every visitor can recompute the hashes and check the signature in the browser.

```bash
modeldiffr registry build audits --out registry_site --key acme=keys/acme.pub
python -m http.server --directory registry_site 8000
```

```text
wrote registry_site with 11 audits
preview: python -m http.server --directory registry_site 8000
```

The site has no server code and no build step. Put the folder on any static host.

## What the build does

1. Finds every `report.json` under the given folders (skipping `_controls`).
2. Runs `modeldiffr verify` on each, with the publisher key when one is given. A report that fails any check is left out and listed in `skipped`, and the command exits with `4`. `--allow-failed` lists it anyway.
3. Copies the report, its HTML page, signatures, timestamps and bills of materials into `audits/<first 16 hex of the audit id>/`.
4. Writes `registry.json` with a summary of each audit and the publisher keys, and the pages that read it.

## What a visitor's browser checks

Opening an audit downloads its `report.json` and recomputes, in plain JavaScript with no server help:

| Check | How |
| --- | --- |
| `audit_id` | RFC 8785 canonical JSON of the manifest, then SHA 256 |
| `manifest_consistency` | Settings and model entries rebuilt from the report |
| `results_root` | RFC 6962 Merkle tree over every per item result |
| `verdict` | Rebuilt from the significance and minimum effect flags |
| `*_weights_leaves` | Merkle root over the per tensor hashes |
| `statement` | SHA 256 over every claim |
| `signature` | Ed25519 signature on `report.dsse.json` with the listed keys, through Web Crypto, and its binding to this report |

The canonical JSON, Merkle and signature code is tested against the Python implementation on every commit, including awkward numbers and Unicode keys. Two checks are left to `modeldiffr verify`: recomputing bootstrap intervals, which needs the same random number generator, and Sigstore bundles, which need the Sigstore trust root. The page says so instead of claiming them.

## Deploy on Netlify

Keep the registry in its own repository, or in a folder of this one, and build it in CI:

```toml netlify.toml
[build]
  command = "pip install modeldiffr[proof] && modeldiffr registry build audits --out registry_site --key acme=keys/acme.pub"
  publish = "registry_site"

[build.environment]
  PYTHON_VERSION = "3.12"
```

Commit `audits/` (reports are small) and the public key, never the private key. Each push rebuilds the site; the generated `_headers` file lets other sites fetch `registry.json` and reports across origins.

GitHub Pages, Cloudflare Pages and S3 work the same way: upload the folder.

## registry.json

```json
{
  "schema": "modeldiffr.registry/1",
  "title": "Modeldiffr audit registry",
  "generated_at": "2026-10-22T10:31:02+00:00",
  "keys": [{"name": "acme", "path": "keys/acme.pub", "pem": "-----BEGIN PUBLIC KEY-----..."}],
  "audits": [
    {
      "id": "71e1c0a4b2d39f10",
      "audit_id": "mdr1:71e1...",
      "base": "Qwen/Qwen2.5-1.5B-Instruct",
      "derivative": "Qwen/Qwen2.5-1.5B-Instruct-GGUF:qwen2.5-1.5b-instruct-q4_k_m.gguf",
      "suite": "lite",
      "verdict": {"any_change": true, "changed": ["gsm8k_accuracy"], "negligible": []},
      "signed": true,
      "anchored": false,
      "files": ["report.json", "report.html", "report.dsse.json"]
    }
  ],
  "skipped": []
}
```

Other tools can read it to show audits next to model listings.
