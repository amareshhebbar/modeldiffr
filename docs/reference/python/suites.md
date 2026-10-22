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
