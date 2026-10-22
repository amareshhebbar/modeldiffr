---
title: Suites and tasks
description: Every benchmark Modeldiffr runs, where its data comes from, and how it is scored.
---

# Suites and tasks

Every benchmark Modeldiffr runs, where its data comes from, and how it is scored.

!!! success "New in 0.3"

    Thirteen standard tasks, three suite sizes, pinned datasets, and deterministic sampling. The built in `quick` suite is unchanged and still needs no downloads.

## Suites

A suite is a list of tasks with a number of items for each. Pick the size from the cost you can afford.

| Task | `lite` | `standard` | `full` |
| --- | --- | --- | --- |
| `mmlu` | 200 | 1,000 | all (14,042) |
| `arc_challenge` | 100 | 500 | all (1,172) |
| `hellaswag` | 100 | 500 | all (10,042) |
| `truthfulqa_mc1` | 100 | all (817) | all |
| `gsm8k` | 50 | 250 | all (1,319) |
| `mgsm` | 50 | 250 | all (2,500) |
| `ifeval` | 50 | 200 | all (541) |
| `xstest_safe` | 50 | all (250) | all |
| `or_bench_hard` | 50 | 250 | all (1,319) |
| `xstest_unsafe` | 50 | all (200) | all |
| `or_bench_toxic` | 50 | 200 | all (655) |
| `humaneval` | | 100 | all (164) |
| `needle` | | 20 | all (108) |
| `divergence` | 50 | 200 | 1,000 |

```bash
modeldiffr audit base derivative --suite lite
modeldiffr audit base derivative --suite standard --tasks mmlu,gsm8k,ifeval
modeldiffr audit base derivative --suite standard --limit 100
```

`--tasks` keeps only the named tasks. `--limit` caps every task at that many items. `modeldiffr suites` and `modeldiffr tasks` list everything.

`humaneval` runs model written code and is skipped unless you pass `--allow-code-execution`. See [Code execution](#code-execution).

## Tasks

| Task | Measures | Dataset (pinned commit) | Scoring | Metrics |
| --- | --- | --- | --- | --- |
| `mmlu` | Knowledge across 57 subjects | `cais/mmlu` all, test, `c30699e8` | Log likelihood of the answer letter | `mmlu_accuracy`, `mmlu_ece` |
| `arc_challenge` | Science reasoning | `allenai/ai2_arc` ARC-Challenge, test, `210d026f` | Log likelihood of each answer text | `arc_challenge_accuracy`, `arc_challenge_ece` |
| `hellaswag` | Common sense completion | `Rowan/hellaswag` validation, parquet | Log likelihood of each ending | `hellaswag_accuracy`, `hellaswag_ece` |
| `truthfulqa_mc1` | Avoiding common falsehoods | `truthfulqa/truthful_qa` multiple_choice, `741b8276` | Log likelihood, single true answer | `truthfulqa_mc1_accuracy`, `truthfulqa_mc1_ece` |
| `gsm8k` | Multi step math | `openai/gsm8k` main, test, `740312ad` | Greedy generation, final number exact match | `gsm8k_accuracy` |
| `mgsm` | Math in ten languages | `juletxara/mgsm` bn de es fr ja ru sw te th zh, parquet | Same as GSM8K | `mgsm_accuracy` |
| `ifeval` | Following formatting instructions | `google/IFEval`, `966cd895` | Rule checks on the response, strict prompt level | `ifeval_prompt_accuracy` |
| `xstest_safe` | Refusing harmless prompts that sound unsafe | `natolambert/xstest-v2-copy`, `b71afe2a` | Refusal detector | `xstest_safe_over_refusal_rate` |
| `or_bench_hard` | Over refusal on hard harmless prompts | `bench-llm/or-bench` or-bench-hard-1k, `e36d8b80` | Refusal detector | `or_bench_hard_over_refusal_rate` |
| `xstest_unsafe` | Complying with unsafe contrast prompts | `natolambert/xstest-v2-copy`, `b71afe2a` | Refusal detector | `xstest_unsafe_compliance_rate` |
| `or_bench_toxic` | Complying with harmful prompts | `bench-llm/or-bench` or-bench-toxic, `e36d8b80` | Refusal detector | `or_bench_toxic_compliance_rate` |
| `humaneval` | Writing correct Python | `openai/openai_humaneval`, `7dce6050` | Raw completion, unit tests in a sandbox | `humaneval_pass_at_1` |
| `needle` | Using long context | Built in, 108 documents of 512 to 4,096 words | Exact match of a hidden code | `needle_accuracy` |
| `divergence` | How much the output distribution moved | Built in sentences and MMLU questions | Mean token level KL | `output_divergence_kl` |

Datasets are fetched at the pinned commit the first time they are used and cached by Hugging Face `datasets`. `hellaswag` and `mgsm` are read from the Hub's parquet conversion because their original repositories use loading scripts. Install the loader with `pip install "modeldiffr[tasks]"`.

### Multiple choice

Every option is scored by the summed log probability of its tokens after the prompt, and the highest one is the prediction. Nothing is parsed from generated text. The probability of the chosen option, after a softmax over the options, is its confidence, which feeds the calibration metric:

```text
ECE = sum over 10 confidence bins of (share of items in bin) x |accuracy in bin - mean confidence in bin|
```

### Generation

Math, IFEval, refusal and needle prompts go through the chat template and greedy decoding. When the two models' templates differ, both receive text rendered with one template, see [Comparable prompts](proof.md#comparable-prompts). Math answers are read from `The answer is N`, or the last number in the response.

### IFEval

25 instruction types are checked with rules reimplemented from Google's reference evaluation, without extra dependencies. Sentence and word splitting are simpler than the reference, so a few borderline responses can be judged differently. `language:response_language` needs `langdetect`; without it that instruction is counted as unsupported and the prompt is scored on the rest. The metric is strict prompt level accuracy: every checkable instruction must be followed.

### Refusal

Responses are classified as refused or answered by a refusal detector:

| Detector | Use |
| --- | --- |
| `keyword` (default) | Regular expressions for common refusal phrases. Fast, no model, misses polite or indirect refusals |
| `hf:MODEL_ID[@LABEL]` | Any Hugging Face text classification model, for example `hf:ProtectAI/distilroberta-base-rejection-v1`. `LABEL` is the class that means refused, default `REJECTION` |

```bash
modeldiffr audit base derivative --suite lite --refusal-detector hf:ProtectAI/distilroberta-base-rejection-v1
```

The detector name is part of the manifest, so it changes the audit id. Measure a detector on your own labeled responses with [`modeldiffr refusal-eval`](../reference/cli/other.md#refusal-eval).

### Code execution

`humaneval` runs each completion and the task's tests in a separate Python process with no inherited environment, a temporary working directory, a 10 second timeout, and limits on memory, processes and file size. This reduces risk but is not a full sandbox; the process can still reach the network. Run it on a machine or container you can throw away.

### Needle

Each document hides `The secret code for the archive room is NNNN.` at 10%, 50% or 90% depth. Documents that would not fit in the smaller of the two models' context windows are dropped before sampling, and the limit used is stored as `settings.context_limit`.

## Deterministic sampling

When a suite takes fewer items than a dataset has, items are chosen by sorting on `SHA256(task || item id)` and taking the first `n`. The choice does not depend on dataset order, it is the same on every machine, and a smaller sample is always a subset of a larger one, so a `lite` run's items are all inside the `standard` run's.

Every chosen item is hashed into the suite root, so the audit id changes if the data behind a pinned name ever changes.

## Offline data

Put one `TASK.jsonl` file per task, in the dataset's own column format, in a folder and pass `--data-dir`:

```bash
modeldiffr audit base derivative --suite lite --data-dir ./benchmarks
```

With `--data-dir`, nothing is downloaded: a missing file is an error. For `mgsm`, use one file per language, `mgsm_de.jsonl` and so on. `MODELDIFFR_DATA_DIR` sets a default folder.

## Plan before running

Every audit prints a plan before it starts: items per task and the smallest change each task can detect at 80% power. `--plan-only` stops there, and with `--estimate` it also times a few calls on your hardware and prints the expected run time:

```bash
modeldiffr audit base derivative --suite standard --plan-only --estimate
```

See [Statistics](statistics.md#power).
