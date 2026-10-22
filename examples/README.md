# Examples

## Instruct model compared with its base

```bash
pip install "modeldiffr[hf]"
python examples/quick_audit.py Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B
```

This pair is small enough to run on a laptop CPU in a few minutes, and it shows what an instruction tuning delta looks like: a large output divergence, usually with a shift in refusal behavior.

## Sanity check: a model compared with itself

```bash
modeldiffr audit Qwen/Qwen2.5-0.5B-Instruct Qwen/Qwen2.5-0.5B-Instruct
```

Every metric should read "within noise". If it does not, something in the setup is not deterministic, and that is worth a bug report.

## Planted regressions

```bash
pip install "modeldiffr[hf,tasks]" pyyaml
modeldiffr batch examples/controls.yaml
```

Three identical copies and eight perturbed copies of Qwen2.5 0.5B Instruct, each audited on the `lite` suite. The summary line reports how many planted changes were found and how many identical copies were flagged. See [Positive controls](https://modeldiffr.netlify.app/guides/controls/).

## A set of public audits

```bash
modeldiffr keygen --out keys
modeldiffr batch examples/public_audits.yaml
modeldiffr registry build audits --out registry_site --key modeldiffr=keys/modeldiffr.pub
```

Official GGUF quants, abliterated models, instruction tunes and a distillation, all under 2B parameters, plus two controls. `gemma-3-1b-it` is gated: accept its license on the Hub and run `huggingface-cli login` first. See [Public registry](https://modeldiffr.netlify.app/guides/registry/).
