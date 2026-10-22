---
title: Run on Colab
description: Run the lite suite on a free GPU in a notebook.
---

# Run on Colab

Run the lite suite on a free GPU in a notebook.

[Open the notebook in Colab](https://colab.research.google.com/github/amareshhebbar/modeldiffr/blob/main/notebooks/colab_lite_audit.ipynb){ .md-button .md-button--primary }

The notebook audits Qwen2.5 0.5B Instruct against its base model with the `lite` suite on a T4:

1. Installs `modeldiffr[hf,tasks,proof]`.
2. Prints the plan: items per task, the smallest change each can detect, and the expected run time on that GPU.
3. Runs the audit in float16.
4. Verifies the report, including rebuilding the suite from the pinned datasets and hashing the weights on the Hub.
5. Shows the metrics as a table and the full HTML report, and downloads both.

Change `BASE` and `DERIVATIVE` in the plan cell to audit your own pair. Both models are held in GPU memory at once, so pairs up to about 1.5B parameters each fit a T4 in float16; for larger models, use a bigger GPU or the [vLLM backend](backends.md).
