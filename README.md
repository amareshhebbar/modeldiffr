<div align="center">

<a href="https://modeldiffr.netlify.app">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/amareshhebbar/modeldiffr/main/docs/logo/dark.svg">
    <img alt="Modeldiffr" src="https://raw.githubusercontent.com/amareshhebbar/modeldiffr/main/docs/logo/light.svg" height="44">
  </picture>
</a>

### Know what changed between a model and anything built from it.

[![PyPI](https://img.shields.io/pypi/v/modeldiffr?color=18202B)](https://pypi.org/project/modeldiffr/)
[![Python](https://img.shields.io/pypi/pyversions/modeldiffr?color=18202B)](https://pypi.org/project/modeldiffr/)
[![CI](https://img.shields.io/github/actions/workflow/status/amareshhebbar/modeldiffr/ci.yml?branch=main&label=CI)](https://github.com/amareshhebbar/modeldiffr/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-modeldiffr.netlify.app-2D5BD7)](https://modeldiffr.netlify.app)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23587023.svg)](https://doi.org/10.5281/zenodo.23587023)
[![License](https://img.shields.io/github/license/amareshhebbar/modeldiffr?color=18202B)](LICENSE)

**[Documentation](https://modeldiffr.netlify.app)** |
[Quickstart](https://modeldiffr.netlify.app/quickstart/) |
[CLI reference](https://modeldiffr.netlify.app/reference/cli/overview/) |
[Roadmap](https://modeldiffr.netlify.app/roadmap/) |
[Report a bug](https://github.com/amareshhebbar/modeldiffr/issues/new?template=bug_report.yml) |
[Contact](https://modeldiffr.netlify.app/support/)

</div>

Modeldiffr audits a **derivative** language model against its **base**: a fine tune, a quantized build, a merge or an edited checkpoint. Both models answer the same items under the same template. Every change comes with a paired interval, and the report is bound to the exact weights, so anyone can verify it.

```bash
pip install "modeldiffr[hf]"
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct your-org/your-qwen-finetune
```

> **Preview, v0.9.** Every layer has shipped. Version 1.0 waits for the published study and model zoo results described in the [roadmap](https://modeldiffr.netlify.app/roadmap/). Report schema 0.3 is the 1.0 candidate.

## Why

Hugging Face hosts hundreds of thousands of derivative models. A model card might say "fine tuned for medical Q&A" or "4 bit, near lossless", but nobody can cheaply check whether general capability dropped, whether safety behavior shifted, or whether a merge is actually better than its parents. Benchmarks run by hand show that a score moved, not whether the move is real, and comparisons are often unfair because prompts, templates or decoding settings differ between runs.

Modeldiffr makes the comparison fair, statistical, repeatable and checkable.

## What it answers

| Question | Commands | Read more |
| --- | --- | --- |
| Which exact models, items and settings were compared, and can anyone check that? | `verify` `sign` `anchor` | [Fingerprints and proof](https://modeldiffr.netlify.app/concepts/proof/), [Attestations](https://modeldiffr.netlify.app/concepts/attestation/) |
| What changed on thirteen standard benchmarks, and is it larger than noise? | `audit` | [Statistics](https://modeldiffr.netlify.app/concepts/statistics/), [Suites](https://modeldiffr.netlify.app/concepts/suites/) |
| Which layers moved, and which features are new, lost or reshaped? | `layers` `features` | [Representational layer](https://modeldiffr.netlify.app/concepts/representational/) |
| How much of a behavioral change do those layers and features carry? | `causal` | [Causal layer](https://modeldiffr.netlify.app/concepts/causal/) |
| Is there an input where the derivative behaves unlike its base? | `scan` `zoo` | [Anomaly scan](https://modeldiffr.netlify.app/concepts/anomaly/) |

Every behavioral metric is a **paired delta with a 95% bootstrap interval**, corrected for multiple comparisons, with a minimum effect below which a change is called negligible. Identical models produce a clean report.

## Install

```bash
pip install "modeldiffr[hf]"
```

| Extra | Adds | Use it for |
| --- | --- | --- |
| `hf` | PyTorch, Transformers | Running audits and the interpretability commands |
| `tasks` | Datasets | The `lite`, `standard` and `full` suites |
| `vllm`, `llamacpp` | vLLM, llama.cpp | Fast GPU generation, GGUF builds |
| `proof` | jsonschema | Full schema checks in `verify` |
| `sign`, `anchor` | cryptography, Sigstore, OpenTimestamps, web3 | Signing and public timestamps |
| `batch` | PyYAML | YAML batch specs |
| `all` | Everything above except vLLM and llama.cpp | |

The core package has no dependencies, which keeps it light for CI jobs that only read reports. See [Installation](https://modeldiffr.netlify.app/installation/).

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

*These numbers show the format only. Run the command to get real values for your models.*

`report.html` is a self contained page you can open anywhere or attach to a pull request. `report.json` holds every item, setting and hash. Full walkthrough: [Quickstart](https://modeldiffr.netlify.app/quickstart/).

## Common tasks

### Run standard benchmarks

```bash
pip install "modeldiffr[hf,tasks]"
modeldiffr audit BASE DERIVATIVE --suite standard --plan-only --estimate
modeldiffr audit BASE DERIVATIVE --suite standard
```

MMLU, ARC Challenge, HellaSwag, TruthfulQA, GSM8K, MGSM, IFEval, XSTest, OR Bench, HumanEval, a long context needle test and output divergence, every dataset pinned to a commit. Try it on a free GPU with the [Colab notebook](notebooks/colab_lite_audit.ipynb). See [Suites and tasks](https://modeldiffr.netlify.app/concepts/suites/).

### Audit a quantized build

```bash
modeldiffr audit Qwen/Qwen2.5-1.5B-Instruct \
  Qwen/Qwen2.5-1.5B-Instruct-GGUF:qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --base-backend hf --suite lite
```

See [Backends](https://modeldiffr.netlify.app/guides/backends/).

### Verify any report

```bash
modeldiffr verify report.json
modeldiffr verify report.json --models
```

`--models` also hashes the real model files at the recorded commits. See [Verify a report](https://modeldiffr.netlify.app/guides/verify/).

### Sign and publish

```bash
modeldiffr keygen --out keys
modeldiffr sign report.json --key keys/modeldiffr.key
modeldiffr hub push audit --repo your-org/your-model
modeldiffr registry build audits --out registry_site --key me=keys/modeldiffr.pub
```

See [Sign and verify](https://modeldiffr.netlify.app/guides/signing/), [Publish an audit](https://modeldiffr.netlify.app/guides/publishing/) and [Public registry](https://modeldiffr.netlify.app/guides/registry/).

### Look inside the model

```bash
modeldiffr layers BASE DERIVATIVE
modeldiffr features BASE DERIVATIVE --layer 14 --out audit --report audit/report.json
modeldiffr causal BASE DERIVATIVE --layer 14 --features audit --tasks mmlu --out audit
modeldiffr scan BASE DERIVATIVE --out audit
```

See [Find changed features](https://modeldiffr.netlify.app/guides/features/), [Test what drives a change](https://modeldiffr.netlify.app/guides/causal/) and [Scan for hidden behavior](https://modeldiffr.netlify.app/guides/scan/).

### Gate a checkpoint in CI

```yaml
permissions:
  id-token: write
  contents: read
steps:
  - uses: actions/checkout@v4
  - uses: amareshhebbar/modeldiffr@v0.9.2
    with:
      base: org/base_model
      derivative: ./checkpoints/candidate
      suite: lite
```

The action audits, fails the job on a significant change, signs the report with Sigstore and uploads it. See [GitHub Action](https://modeldiffr.netlify.app/guides/publishing/#github-action) and [CI gate](https://modeldiffr.netlify.app/guides/ci_gate/).

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

## How it works

1. Both models are fingerprinted (weights, tokenizer, chat template) and checked for comparability. The audit gets an id computed from everything that defines it, before anything runs.
2. Both models run on exactly the same inputs, with one shared chat template when theirs differ.
3. Multiple choice items are scored by log likelihood, so the result does not depend on answer formatting.
4. Paired bootstrap resampling turns per item results into deltas with intervals and p values, corrected across all metrics.
5. Every item and result is committed to in a Merkle tree, and a statement hash covers every claim, so `modeldiffr verify` can recompute the report.
6. Optional layers look inside: crosscoders for features, patching for causal shares, and a scan for unusual inputs.

Details: [How it works](https://modeldiffr.netlify.app/concepts/how_it_works/).

## Roadmap

| Version | Shipped |
| --- | --- |
| 0.2 | Weight fingerprints, audit ids, `verify` |
| 0.3 | Thirteen benchmarks, four backends, corrected statistics |
| 0.4 | Signing, in toto attestations, public timestamps, bills of materials, GitHub Action, Hub upload |
| 0.5 | Planted regression controls, batch audits, a registry that verifies in the browser |
| 0.6 | Layer statistics, direction comparison, crosscoders with new, lost and shifted features |
| 0.7 | Layer and feature patching and steering |
| 0.8 | Anomaly scan and a model zoo that measures its accuracy |
| 0.9 | Study tables, JSON Schemas, compatibility promise, governance, report draft |
| 1.0 | When the public study and zoo results are published |

Full plan: [Roadmap](https://modeldiffr.netlify.app/roadmap/) and [PLAN.md](PLAN.md).

## Limitations

* The built in `quick` suite is a smoke test. Use `lite`, `standard` or `full` for a release decision.
* Large models need a GPU. Both models are held in memory at once.
* A significant change shows that something moved, not why. Features and causal shares are leads, not proofs.
* The anomaly scan makes no claim about real models until its rates on a public zoo are published.

All of them: [Limitations](https://modeldiffr.netlify.app/limitations/).

## Help and contact

| Need | Where |
| --- | --- |
| Something is broken | [Report a bug](https://github.com/amareshhebbar/modeldiffr/issues/new?template=bug_report.yml) |
| A metric, suite or backend you need | [Request a feature](https://github.com/amareshhebbar/modeldiffr/issues/new?template=feature_request.yml) |
| Usage questions | [GitHub Discussions](https://github.com/amareshhebbar/modeldiffr/discussions) |
| A security issue | [Private advisory](https://github.com/amareshhebbar/modeldiffr/security/advisories/new), see [SECURITY.md](SECURITY.md) |
| Audits of your models, collaboration, anything else | [hebbar.gvamaresh@gmail.com](mailto:hebbar.gvamaresh@gmail.com?subject=Modeldiffr) |

More: [Contact and support](https://modeldiffr.netlify.app/support/).

## Responsible use

Modeldiffr is a measurement tool. It never modifies model weights, and its reports describe *what* changed and *how much*, not how to reproduce or reverse a change. If you find a serious safety regression or hidden behavior in a public model, please contact its publisher before posting the finding. See [Responsible use](https://modeldiffr.netlify.app/responsible_use/).

## Contributing

Contributions are welcome, from bug reports to new evaluation suites. Start with [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md) and issues labelled `good first issue`.

## Citation

If Modeldiffr helps your research, please cite it using [CITATION.cff](CITATION.cff) or:

```bibtex
@software{hebbar_modeldiffr_2026,
  author  = {Hebbar, Amaresh},
  title   = {Modeldiffr: auditing what changes between base and derivative language models},
  year    = {2026},
  url     = {https://github.com/amareshhebbar/modeldiffr},
  version = {0.9.2},
  doi     = {10.5281/zenodo.23587023}
}
```

## Acknowledgements

The representational layer builds on crosscoder based model diffing, introduced in *Sparse Crosscoders for Cross Layer Features and Model Diffing* (Lindsey et al., Anthropic, 2024), and on the work that followed it. Behavioral evaluation draws on open harnesses such as EleutherAI's lm evaluation harness and UK AISI's Inspect. The proof layer follows RFC 8785 and RFC 6962 and interoperates with Sigstore and in toto.

## License

[Apache 2.0](LICENSE). Copyright 2026 Amaresh Hebbar.
