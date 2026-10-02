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
