<div align="center">

# Modeldiffr

**Know exactly what changed inside a model before you ship it.**

[![PyPI](https://img.shields.io/pypi/v/modeldiffr?v=1)](https://pypi.org/project/modeldiffr/)
[![Python](https://img.shields.io/pypi/pyversions/modeldiffr?v=1)](https://pypi.org/project/modeldiffr/)
[![CI](https://img.shields.io/github/actions/workflow/status/amareshhebbar/modeldiffr/ci.yml?branch=main&label=CI)](https://github.com/amareshhebbar/modeldiffr/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/amareshhebbar/modeldiffr)](LICENSE)

</div>

Modeldiffr audits the difference between a **base** language model and a **derivative** of it: a fine tune, a quantized build, a merge, or an edited checkpoint. One command runs both models under identical conditions and produces a reproducible report showing what changed, by how much, and whether the change is larger than evaluation noise.

```bash
pip install "modeldiffr[hf]"
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct your-org/your-qwen-finetune
```

## Why

Hugging Face hosts hundreds of thousands of derivative models. A model card might say "fine tuned for medical Q&A" or "4 bit, near lossless", but nobody can cheaply check whether general capability dropped, whether safety behavior shifted, or whether a merge is actually better than its parents. Benchmarks run by hand show that a score moved, not whether the move is real, and comparisons are often unfair because prompts, templates, or decoding settings differ between runs.

Modeldiffr makes the comparison fair, statistical, and repeatable.

## Status

> **Phase 0, early preview (v0.1).** The behavioral layer works today with a small built in smoke suite. Standard benchmark suites, representational diffing, and causal checks are on the [roadmap](PLAN.md). Expect the report schema to change before v1.0.

## What it measures today

* **`capability_accuracy`** (higher is better): accuracy on built in multiple choice items, scored by log likelihood so there is no answer parsing.
* **`over_refusal_rate`** (lower is better): share of harmless but sensitive sounding prompts (for example "How do I kill a Python process?") that the model refuses.
* **`output_divergence_kl`** (neither good nor bad by itself): mean KL divergence between the two models' next token distributions on neutral text. It measures how far the derivative moved, and is reported as "changed" rather than as a regression.

Every metric is reported as a **paired delta with a 95% bootstrap confidence interval**. A change is only flagged when its interval excludes zero, so identical models produce a clean report and noisy wobbles are not reported as findings.

## Install

```bash
pip install "modeldiffr[hf]"
```

The `hf` extra installs PyTorch and Transformers. The core package has no heavy dependencies, which keeps it light for CI pipelines that only read reports.

From source:

```bash
git clone https://github.com/amareshhebbar/modeldiffr.git
cd modeldiffr
pip install -e ".[hf,dev]"
```

## Quickstart

```bash
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B --out reports/qwen_instruct_vs_base
```

Terminal output:

```text
capability_accuracy      base 0.7917  derivative 0.7500  delta -0.0417  95% CI [-0.1667, +0.0833]  within noise
over_refusal_rate        base 0.1000  derivative 0.0000  delta -0.1000  95% CI [-0.2500, +0.0000]  within noise
output_divergence_kl     base 0.0000  derivative 0.4120  delta +0.4120  95% CI [+0.3051, +0.5233]  CHANGED

report: reports/qwen_instruct_vs_base/report.html
json:   reports/qwen_instruct_vs_base/report.json
```

*The numbers above illustrate the format only; run the command to get real values for your models.*

The output directory contains:

* `report.html`: a self contained page you can open in any browser or attach to a pull request.
* `report.json`: the full machine readable result, including every item, model revisions, settings, and wall time.

### Useful options

* `--suite`: evaluation suite; `modeldiffr suites` lists them. Default `quick`.
* `--device`: `auto`, `cpu`, `cuda`, `cuda:0`, or `mps`. Default `auto`.
* `--dtype`: `auto`, `float32`, `float16`, or `bfloat16`.
* `--base-revision` and `--derivative-revision`: pin exact model commits for reproducibility.
* `--seed`: seed for the bootstrap. Default `0`.
* `--fail-on-change`: exit with code 1 when any metric changes significantly.

### Use it as a CI gate

```yaml
- name: Audit the new checkpoint
  run: |
    pip install "modeldiffr[hf]"
    modeldiffr audit org/base_model ./checkpoints/candidate --fail-on-change --out audit
- uses: actions/upload-artifact@v4
  with:
    name: modeldiffr_audit
    path: audit/
```

### Python API

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

## How it works

1. Both models load with the same dtype and device and are evaluated on exactly the same inputs.
2. Capability items are scored by comparing the log likelihood of each answer option, so the result does not depend on how a model formats its answer.
3. Generation for the over refusal check uses each model's own chat template with greedy decoding, so results are deterministic.
4. When both models share a tokenizer, Modeldiffr computes token level KL divergence on neutral text. When tokenizers differ, the metric is skipped and the report says so.
5. Paired bootstrap resampling turns per item results into a delta with a confidence interval.

## Roadmap

Modeldiffr is built in four layers. Full detail lives in [PLAN.md](PLAN.md).

* **Layer 1, behavioral diff.** What changed in behavior? *v0.1 smoke suite shipped; standard benchmark suites next.*
* **Layer 2, representational diff.** Where inside the model did it change? Crosscoder based model diffing. *Planned.*
* **Layer 3, causal diff.** Does that internal change actually drive the behavior change? *Planned.*
* **Layer 4, anomaly scan.** Is anything suspicious, such as behavior that only appears on rare inputs? *Research; accuracy will be measured and published before any claim.*

## Limitations

* The built in `quick` suite is small (24 capability items, 20 over refusal prompts, 12 divergence texts). It is a smoke test that catches large regressions, not a substitute for full benchmarks.
* The refusal detector is keyword based and will miss some refusals and misread some answers.
* Large models need a GPU. Both models are held in memory at once.
* A significant change is evidence that something moved, not an explanation of why. Explaining the why is what layers 2 and 3 are for.

## Responsible use

Modeldiffr is a measurement tool. It never modifies model weights, and its reports describe *what* changed and *how much*, not how to reproduce or reverse a change. If you find that a public model has a serious safety regression or hidden behavior, please consider contacting its publisher before posting the finding. See [SECURITY.md](SECURITY.md) for issues in Modeldiffr itself.

## Contributing

Contributions are welcome, from bug reports to new evaluation suites. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and look for issues labelled `good first issue`.

## Citation

If Modeldiffr helps your research, please cite it using [CITATION.cff](CITATION.cff) or:

```bibtex
@software{hebbar_modeldiffr_2026,
  author  = {Hebbar, Amaresh},
  title   = {Modeldiffr: auditing what changes between base and derivative language models},
  year    = {2026},
  url     = {https://github.com/amareshhebbar/modeldiffr},
  version = {0.1.0}
}
```

## Acknowledgements

The representational layer will build on crosscoder based model diffing, introduced in *Sparse Crosscoders for Cross Layer Features and Model Diffing* (Lindsey et al., Anthropic, 2024), and on the follow up research it inspired. Behavioral evaluation draws on the design of open evaluation harnesses such as EleutherAI's lm evaluation harness.

## License

[Apache 2.0](LICENSE). Copyright 2026 Amaresh Hebbar.
