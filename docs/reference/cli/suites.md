---
title: modeldiffr suites
description: List available evaluation suites.
---

# modeldiffr suites

List available evaluation suites.

```bash
modeldiffr suites
```

Prints one line per registered suite with its item counts. Needs only the core package.

```text
quick: 24 capability items, 20 over refusal prompts, 12 divergence texts
```

## Built in suites

| Suite | Capability | Over refusal | Divergence | max_new_tokens |
| --- | --- | --- | --- | --- |
| `quick` | 24 | 20 | 12 | 64 |

The `quick` suite is a smoke test for fast checks on small models. It covers arithmetic, geography, science, basic programming, and simple reasoning. Standard benchmark suites arrive in a later release.

To add your own, see [Custom suites](../../guides/custom_suite.md).
