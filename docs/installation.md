---
title: Installation
description: Install Modeldiffr from PyPI or from source.
---

# Installation

Install Modeldiffr from PyPI or from source.

## Requirements

* Python 3.10, 3.11, or 3.12
* A GPU for anything larger than a small model. Both models are held in memory at once.

## Install from PyPI

=== "With model support"

    ```bash
    pip install "modeldiffr[hf]"
    ```
    The `hf` extra installs `torch>=2.1`, `transformers>=4.40`, `accelerate>=0.30` and `huggingface_hub`. Use this to run audits.

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

=== "Verify reports only"

    ```bash
    pip install "modeldiffr[proof]"
    ```
    No GPU and no PyTorch. Enough to run `modeldiffr verify report.json` with the full schema check.

=== "Core only"

    ```bash
    pip install modeldiffr
    ```
    The core package has no dependencies. It is enough for CI jobs that only read `report.json`, and for the statistics in `modeldiffr.stats`.

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
modeldiffr 0.1.0
quick: 24 capability items, 20 over refusal prompts, 12 divergence texts
```

You can also run the package as a module:

```bash
python -m modeldiffr --version
```

## Device support

`--device auto` picks the first available option in this order:

1. `cuda`
2. `mps` (Apple Silicon)
3. `cpu`

Pass an explicit value such as `cuda:0` to override.
