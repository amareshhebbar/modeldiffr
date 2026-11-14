<div align="center">

<a href="https://modeldiffr.readthedocs.io/en/latest/">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/amareshhebbar/modeldiffr/main/docs/logo/dark.svg">
    <img alt="Modeldiffr" src="https://raw.githubusercontent.com/amareshhebbar/modeldiffr/main/docs/logo/light.svg" height="44">
  </picture>
</a>

### Find out what really changed when someone fine tuned, quantized, merged or edited a model.

[![Read the Docs](https://readthedocs.org/projects/modeldiffr/badge/?version=latest)](https://modeldiffr.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/modeldiffr?color=18202B)](https://pypi.org/project/modeldiffr/)
[![Python](https://img.shields.io/pypi/pyversions/modeldiffr?color=18202B)](https://pypi.org/project/modeldiffr/)
[![CI](https://img.shields.io/github/actions/workflow/status/amareshhebbar/modeldiffr/ci.yml?branch=main&label=CI)](https://github.com/amareshhebbar/modeldiffr/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-modeldiffr.netlify.app-2D5BD7)](https://modeldiffr.netlify.app)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23587022.svg)](https://doi.org/10.5281/zenodo.23587022)
[![License](https://img.shields.io/github/license/amareshhebbar/modeldiffr?color=18202B)](LICENSE)

**[Documentation](https://modeldiffr.readthedocs.io/en/latest/)** |
[Quickstart](https://modeldiffr.netlify.app/quickstart/) |
[How it works](https://modeldiffr.netlify.app/concepts/how_it_works/) |
[Layer by layer](https://modeldiffr.netlify.app/concepts/layer_by_layer/) |
[CLI reference](https://modeldiffr.netlify.app/reference/cli/overview/) |
[Roadmap](https://modeldiffr.netlify.app/roadmap/)

</div>

## What is this?

You start with a model, the **base**. Someone builds a new model from it, the **derivative**. That can be a fine tune, a 4 bit quantized build, a merge of two models, or a model with some behavior edited out.

The model card usually says something like "fine tuned for medical questions" or "4 bit, almost no quality loss". Modeldiffr checks that claim. It gives both models the exact same questions, compares the answers, tells you which differences are real and which are just noise, and writes a report that anyone can check later.

```bash
pip install "modeldiffr[hf]"
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct your-org/your-qwen-finetune
```

> **Status: v0.9 preview.** All the features are built. Version 1.0 comes after the public study and the backdoor test results are published. See the [roadmap](https://modeldiffr.netlify.app/roadmap/).

## Why you need it

Hugging Face has hundreds of thousands of derivative models. Picking one today means trusting a sentence on a model card. Running benchmarks yourself is not much better, for three reasons:

1. **Unfair setup.** The two models often get different prompts, chat templates or settings. Then you are measuring the setup, not the model.
2. **No sense of noise.** A score that moves from 79% to 75% on 24 questions could easily be luck. A plain benchmark number does not tell you.
3. **No way to check.** Someone posts a table of results. You cannot tell which exact weights they ran, or whether the numbers were edited.

Modeldiffr fixes all three. Same inputs for both models, a confidence range on every number, and a report that is locked to the exact model files.

## How it works, in plain words

Think of it as a careful experiment where the **only** thing that changes is the model.

1. **Take fingerprints.** Modeldiffr hashes every weight tensor, the tokenizer and the chat template of both models. Now the report points to the exact files, not just a name on the Hub that someone could overwrite.
2. **Ask the same questions.** Both models get byte for byte identical prompts. If their chat templates differ, both get the prompt written with one shared template.
3. **Score fairly.** For multiple choice questions, Modeldiffr does not read the model's written answer. It asks the model how likely each option is and picks the most likely one. So a model that writes "Sure! The answer is B" is not punished for its style.
4. **Separate real change from luck.** For every question it looks at the difference between the two models. Then it reshuffles those differences thousands of times (a bootstrap) to see how much the average could move by chance. If the range of likely values does not include zero, the change is real.
5. **Lock the report.** Every question and every answer is hashed into one summary hash (a Merkle tree). If anyone edits a single number later, `modeldiffr verify` will catch it.
6. **Look inside, if you want.** Optional tools compare the models layer by layer, find which internal features are new or lost, test which of them actually cause the behavior change, and scan for hidden triggers.

Longer version: [How it works](https://modeldiffr.netlify.app/concepts/how_it_works/).

## Layer by layer comparison

Benchmarks tell you **that** something changed. The layer by layer tools tell you **where** inside the model it changed.

There are two views:

| View | Command | What it compares | Needs to run the model? |
| --- | --- | --- | --- |
| Weights | runs inside every `audit`, and `fingerprint` | The stored numbers of every tensor, one by one | No |
| Hidden states | `modeldiffr layers` | What each layer actually outputs when both models read the same text | Yes |

**The weights view** hashes each tensor in both models and lists which ones are different, added or removed. A LoRA fine tune that only touched attention shows up as "only attention tensors changed". A "near lossless" quant shows up as "every tensor changed". You learn this before any benchmark runs.

**The hidden states view** feeds the same text to both models and records what each layer outputs for every token. Then, for each layer, it measures how similar the two outputs are:

| Number | Plain meaning | Identical models give |
| --- | --- | --- |
| `cka` | Do the two layers organize the information the same way overall? | 1 |
| `cosine` | Do the token vectors point in the same direction? | 1 |
| `relative_change` | How big is the difference, compared to the size of the base output? | 0 |
| `mean_shift` | Did the average output move? | 0 |
| `norm_ratio` | Did the outputs get bigger or smaller? | 1 |

```bash
modeldiffr layers Qwen/Qwen2.5-0.5B-Instruct your-org/your-qwen-finetune
```

```text
layer      CKA   cosine  rel change  mean shift  norm ratio
    0   1.0000   1.0000      0.0000      0.0000      1.0000
   ...
   14   0.9871   0.9802      0.1543      0.0611      0.9930
   ...
largest change at layer 14
```

**Why this works.** A transformer is a stack of layers. Each layer reads the output of the one before it and passes its own output on. If two models read the exact same tokens, any difference at layer N must come from weights at layer N or before it. So the first layer where the numbers jump is where the derivative starts thinking differently. Small fine tunes usually leave early layers almost untouched and show a clear jump somewhere in the middle.

**Why it is needed.** Two models can score the same on every benchmark and still be different inside. A quant might lose precision in one specific layer. An "abliterated" model might keep its benchmark scores but have its refusal behavior cut out at a few layers. The layer view finds those places, and tells the more expensive tools (crosscoders and causal patching) which layer to study.

Full explanation: [Layer by layer comparison](https://modeldiffr.netlify.app/concepts/layer_by_layer/).

## What it can answer

| Question | Commands | Read more |
| --- | --- | --- |
| Which exact models and settings were compared, and can anyone check it? | `verify` `sign` `anchor` | [Fingerprints and proof](https://modeldiffr.netlify.app/concepts/proof/) |
| Did scores change on thirteen standard benchmarks, and is the change bigger than noise? | `audit` | [Statistics](https://modeldiffr.netlify.app/concepts/statistics/) |
| Which layers changed, and by how much? | `layers` `directions` | [Layer by layer](https://modeldiffr.netlify.app/concepts/layer_by_layer/) |
| Which internal features are new, lost or reshaped? | `features` | [Features](https://modeldiffr.netlify.app/concepts/representational/) |
| Which of those layers and features actually cause the change? | `causal` | [Causal tests](https://modeldiffr.netlify.app/concepts/causal/) |
| Is there a strange input where the derivative acts very differently? | `scan` `zoo` | [Anomaly scan](https://modeldiffr.netlify.app/concepts/anomaly/) |

## Install

```bash
pip install "modeldiffr[hf]"
```

| Extra | Adds | Use it for |
| --- | --- | --- |
| `hf` | PyTorch, Transformers | Running audits and the layer tools |
| `tasks` | Datasets | The `lite`, `standard` and `full` benchmark suites |
| `vllm`, `llamacpp` | vLLM, llama.cpp | Fast GPU generation, GGUF builds |
| `proof` | jsonschema | Full schema checks in `verify` |
| `sign`, `anchor` | cryptography, Sigstore, OpenTimestamps, web3 | Signing and public timestamps |
| `batch` | PyYAML | YAML batch files |
| `all` | Everything above except vLLM and llama.cpp | |

The core package has no dependencies at all, so a CI job that only reads reports stays tiny. See [Installation](https://modeldiffr.netlify.app/installation/).

## Quickstart

```bash
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B --out reports/qwen
```

```text
audit id mdr1:71e153dc730bb9ec20b7159dc8845afab76de27ddf94b99cada26c713aa3170d
weights: 290 of 290 shared tensors changed, 0 added, 0 removed

capability_accuracy      base 0.7917  derivative 0.7500  delta -0.0417  95% CI [-0.1667, +0.0833]  within noise
over_refusal_rate        base 0.1000  derivative 0.0000  delta -0.1000  95% CI [-0.2500, +0.0000]  within noise
output_divergence_kl     base 0.0000  derivative 0.4120  delta +0.4120  95% CI [+0.3051, +0.5233]  CHANGED

report: reports/qwen/report.html
json:   reports/qwen/report.json
```

*These numbers only show the format. Run the command to get real values.*

How to read one line: `delta` is derivative minus base. `95% CI` is the range the true difference most likely sits in. If that range includes zero, the result is `within noise`. If it does not, the result is `CHANGED`.

`report.html` is a single page you can open anywhere or attach to a pull request. `report.json` holds every question, setting and hash. Full walkthrough: [Quickstart](https://modeldiffr.netlify.app/quickstart/).

## Common tasks

### Run real benchmarks

```bash
pip install "modeldiffr[hf,tasks]"
modeldiffr audit BASE DERIVATIVE --suite standard --plan-only --estimate
modeldiffr audit BASE DERIVATIVE --suite standard
```

Covers MMLU, ARC Challenge, HellaSwag, TruthfulQA, GSM8K, MGSM, IFEval, XSTest, OR Bench, HumanEval, a long context test and output divergence. Every dataset is pinned to a fixed commit. `--plan-only --estimate` tells you how long it will take before you commit a GPU. Try it free on [Colab](notebooks/colab_lite_audit.ipynb).

### Check a quantized build

```bash
modeldiffr audit Qwen/Qwen2.5-1.5B-Instruct \
  Qwen/Qwen2.5-1.5B-Instruct-GGUF:qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --base-backend hf --suite lite
```

See [Backends](https://modeldiffr.netlify.app/guides/backends/).

### Check someone else's report

```bash
modeldiffr verify report.json
modeldiffr verify report.json --models
```

`--models` also downloads and hashes the real model files to confirm they match. See [Verify a report](https://modeldiffr.netlify.app/guides/verify/).

### Sign and publish

```bash
modeldiffr keygen --out keys
modeldiffr sign report.json --key keys/modeldiffr.key
modeldiffr hub push audit --repo your-org/your-model
modeldiffr registry build audits --out registry_site --key me=keys/modeldiffr.pub
```

See [Sign and verify](https://modeldiffr.netlify.app/guides/signing/) and [Public registry](https://modeldiffr.netlify.app/guides/registry/).

### Look inside the model

```bash
modeldiffr layers BASE DERIVATIVE
modeldiffr features BASE DERIVATIVE --layer 14 --out audit --report audit/report.json
modeldiffr causal BASE DERIVATIVE --layer 14 --features audit --tasks mmlu --out audit
modeldiffr scan BASE DERIVATIVE --out audit
```

Run them in this order. `layers` finds the layer, `features` finds what changed at that layer, `causal` tests whether it matters, `scan` looks for hidden triggers.

### Block a bad checkpoint in CI

```yaml
permissions:
  id-token: write
  contents: read
steps:
  - uses: actions/checkout@v4
  - uses: amareshhebbar/modeldiffr@v0.9.3
    with:
      base: org/base_model
      derivative: ./checkpoints/candidate
      suite: lite
```

The action runs the audit, fails the job if something changed for real, signs the report and uploads it. See [CI gate](https://modeldiffr.netlify.app/guides/ci_gate/).

### Use it from Python

```python
from modeldiffr import run_audit
from modeldiffr.backend import HFBackend
from modeldiffr.report import write_reports
from modeldiffr.suites import get_suite

base = HFBackend("Qwen/Qwen2.5-0.5B-Instruct")
derivative = HFBackend("your-org/your-qwen-finetune")
result = run_audit(base, derivative, get_suite("quick"))
write_reports(result, "audit")
print(result["verdict"])
```

See [Python usage](https://modeldiffr.netlify.app/guides/python_usage/).

## Roadmap

| Version | Shipped |
| --- | --- |
| 0.2 | Weight fingerprints, audit ids, `verify` |
| 0.3 | Thirteen benchmarks, four backends, corrected statistics |
| 0.4 | Signing, attestations, public timestamps, bills of materials, GitHub Action, Hub upload |
| 0.5 | Planted change controls, batch audits, a registry that verifies in the browser |
| 0.6 | Layer by layer statistics, direction comparison, crosscoder features |
| 0.7 | Patching and steering tests |
| 0.8 | Anomaly scan and a test zoo that measures its accuracy |
| 0.9 | Study tables, JSON Schemas, compatibility promise, governance, paper draft |
| 1.0 | After the public study and zoo results are published |

What is still open is listed in [Roadmap: still pending](https://modeldiffr.netlify.app/roadmap/#still-pending).

## Limitations

* The built in `quick` suite is a smoke test. Use `lite`, `standard` or `full` for a real decision.
* Bigger models need a GPU. Both models are in memory at the same time.
* A real change tells you something moved, not why. Features and causal shares are strong hints, not final proof.
* The anomaly scan makes no claim about real models until its accuracy on a public zoo is published.

All of them: [Limitations](https://modeldiffr.netlify.app/limitations/).

## Help and contact

| Need | Where |
| --- | --- |
| Something is broken | [Report a bug](https://github.com/amareshhebbar/modeldiffr/issues/new?template=bug_report.yml) |
| A metric, suite or backend you need | [Request a feature](https://github.com/amareshhebbar/modeldiffr/issues/new?template=feature_request.yml) |
| Questions | [GitHub Discussions](https://github.com/amareshhebbar/modeldiffr/discussions) |
| A security issue | [Private advisory](https://github.com/amareshhebbar/modeldiffr/security/advisories/new), see [SECURITY.md](SECURITY.md) |
| Audits of your models, collaboration, anything else | [hebbar.gvamaresh@gmail.com](mailto:hebbar.gvamaresh@gmail.com?subject=Modeldiffr) |

## Responsible use

Modeldiffr only measures. It never changes model weights, and its reports say what changed and by how much, not how to copy or undo a change. If you find a serious safety problem or hidden behavior in a public model, tell its publisher privately before you post about it. See [Responsible use](https://modeldiffr.netlify.app/responsible_use/).

## Contributing

Everything from bug reports to new benchmark suites is welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md) and issues labelled `good first issue`.

## Citation

```bibtex
@software{hebbar_modeldiffr_2026,
  author  = {Hebbar, Amaresh},
  title   = {Modeldiffr: auditing what changes between base and derivative language models},
  year    = {2026},
  url     = {https://github.com/amareshhebbar/modeldiffr},
  version = {0.9.3},
  doi     = {10.5281/zenodo.23587022}
}
```

## Acknowledgements

The feature comparison builds on crosscoder model diffing from *Sparse Crosscoders for Cross Layer Features and Model Diffing* (Lindsey et al., Anthropic, 2024) and the work that followed. The benchmark side learns from EleutherAI's lm evaluation harness and UK AISI's Inspect. The proof side follows RFC 8785 and RFC 6962 and works with Sigstore and in toto.

## License

[Apache 2.0](LICENSE). Copyright 2026 Amaresh Hebbar.