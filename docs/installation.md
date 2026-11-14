---
title: Installation
description: Install Modeldiffr from PyPI or from source.
---

# Installation

Install Modeldiffr from PyPI or from source.

## Requirements

* Python 3.10, 3.11, or 3.12
* A GPU for anything bigger than a small model. Both models are in memory at the same time, so two 7B models in bfloat16 need about 28 GB.

## Install from PyPI

=== "With model support"

    ```bash
    pip install "modeldiffr[hf]"
    ```
    Installs PyTorch, Transformers, Accelerate and the Hugging Face Hub client. You need this to run any model.

=== "Standard benchmarks"

    ```bash
    pip install "modeldiffr[hf,tasks]"
    ```
    Adds `datasets` for the `lite`, `standard` and `full` suites.

=== "vLLM or llama.cpp"

    ```bash
    pip install "modeldiffr[vllm]"
    pip install "modeldiffr[hf,llamacpp]"
    ```
    See [Backends](guides/backends.md).

=== "Everything"

    ```bash
    pip install "modeldiffr[all]"
    ```

=== "Signing and anchors"

    ```bash
    pip install "modeldiffr[proof,sign,anchor]"
    ```
    `sign` adds `cryptography` and `sigstore`; `anchor` adds the OpenTimestamps client and `web3`. See [Sign and verify](guides/signing.md).

=== "Verify reports only"

    ```bash
    pip install "modeldiffr[proof]"
    ```
    No GPU, no PyTorch. Enough to check someone else's report with `modeldiffr verify report.json`.

=== "Core only"

    ```bash
    pip install modeldiffr
    ```
    No dependencies at all. Enough for CI jobs that only read `report.json`, and for the statistics in `modeldiffr.stats`.

!!! warning

    Running `modeldiffr audit` without the `hf` extra exits with code `2` and prints:

    ```text
    error: Hugging Face support is not installed. Run: pip install "modeldiffr[hf]"
    ```

## Install from source

```bash
git clone https://github.com/amareshhebbar/modeldiffr.git
cd modeldiffr
pip install -e ".[hf,dev]"
```

The `dev` extra adds `pytest`, `ruff`, `build`, `twine`, `jsonschema`, `numpy`, `safetensors` and `gguf`.

## Verify

```bash
modeldiffr --version
modeldiffr suites
```

Expected output:

```text
modeldiffr 0.9.3
quick: 24 capability items, 20 over refusal prompts, 12 divergence texts
```

You can also run the package as a module:

```bash
python -m modeldiffr --version
```

## Device support

`--device auto` picks the first one it finds, in this order:

1. `cuda`
2. `mps` (Apple Silicon)
3. `cpu`

Pass a value such as `cuda:0` to choose yourself.