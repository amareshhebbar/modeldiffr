---
title: Suites
description: Suite, ChoiceItem, SUITES, and get_suite.
---

# Suites

Suite, ChoiceItem, SUITES, and get_suite.

```python
from modeldiffr.suites import QUICK, SUITES, ChoiceItem, Suite, get_suite
```

## ChoiceItem

```python
@dataclass(frozen=True)
class ChoiceItem:
    question: str
    choices: tuple[str, ...]
    answer: int
```

- **`question`** *str*: Question text, inserted into `Question: {question}\nAnswer:`.

- **`choices`** *tuple[str, ...]*: Answer options, each scored with a leading space.

- **`answer`** *int*: Zero based index of the correct choice.

## Suite

```python
@dataclass(frozen=True)
class Suite:
    name: str
    capability: tuple[ChoiceItem, ...]
    benign_prompts: tuple[str, ...]
    neutral_texts: tuple[str, ...]
    max_new_tokens: int = 64
    notes: tuple[str, ...] = ()
```

- **`name`** *str*: Identifier used by `--suite` and stored in the report.

- **`capability`** *tuple[ChoiceItem, ...]*: Items for `capability_accuracy`.

- **`benign_prompts`** *tuple[str, ...]*: Prompts for `over_refusal_rate`.

- **`neutral_texts`** *tuple[str, ...]*: Texts for `output_divergence_kl`.

- **`max_new_tokens`** *int*: Generation budget for over refusal.

- **`notes`** *tuple[str, ...]*: Shown in the report.

## SUITES

```python
SUITES: dict[str, Suite] = {"quick": QUICK}
```

Registry used by the CLI and `get_suite`.

## get_suite

```python
get_suite(name: str) -> Suite
```

Returns the registered suite. Raises `KeyError` with the list of available names when `name` is unknown.

```python
get_suite("quick")
```

## QUICK

The built in smoke suite: 24 capability items, 20 benign prompts, 12 neutral texts, `max_new_tokens=64`.

## Benchmark suites

The `lite`, `standard` and `full` suites are built from tasks:

```python
from modeldiffr.tasks import build_tasks, task_suite

suite = task_suite("standard", only=["mmlu", "gsm8k"], limit=200, allow_code_execution=False)
for task, size in suite.entries:
    print(task.name, size, [m.name for m in task.metrics])

tasks = build_tasks()
items = tasks["mmlu"].load()
```

`task_suite(name, only=None, limit=None, allow_code_execution=False)` returns a `TaskSuite` that `run_audit` accepts in place of a `Suite`. Passing a built in suite name such as `quick` wraps it as tasks. Each `Task` has `name`, `kind`, `metrics`, `source` and `max_new_tokens`, `load(data_dir=None)` returns its items, and `run(backend, items, ctx)` returns per item rows. See [Suites and tasks](../../concepts/suites.md).

