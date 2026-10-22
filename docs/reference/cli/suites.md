---
title: modeldiffr suites
description: List available evaluation suites.
---

# modeldiffr suites

List available evaluation suites.

```bash
modeldiffr suites
```

```text
quick: built in, 24 capability items, 20 over refusal prompts, 12 divergence texts
lite: mmlu 200, arc_challenge 100, hellaswag 100, truthfulqa_mc1 100, gsm8k 50, mgsm 50, ifeval 50, ...
standard: mmlu 1000, arc_challenge 500, hellaswag 500, truthfulqa_mc1 all, gsm8k 250, ...
full: mmlu all, arc_challenge all, hellaswag all, ...
```

| Suite | Downloads | Typical use |
| --- | --- | --- |
| `quick` | None | Smoke test, CI on small models, the default |
| `lite` | Datasets, once, then cached | A first real look on a small GPU |
| `standard` | Same datasets | Release decisions |
| `full` | Same datasets | Publication quality audits |

Every task, dataset and size is listed in [Suites and tasks](../../concepts/suites.md). To add your own built in style suite, see [Custom suites](../../guides/custom_suite.md).
