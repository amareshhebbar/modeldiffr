---
title: Summarize a study
description: Turn a folder of audits into tables by derivative kind and by metric, as CSV, Markdown and LaTeX.
---

# Summarize a study

Turn a folder of audits into tables by derivative kind and by metric, as CSV, Markdown and LaTeX.

```bash
modeldiffr batch examples/public_audits.yaml
modeldiffr study audits --out study
```

```text
11 audits, 7 with a significant change
  abliterated        3 audits, 3 changed
  quantization       3 audits, 1 changed
  ...
wrote study/study.md, study.csv, study.tex and study.json
```

These lines show the format. Tag each audit with `kind` in the batch spec (for example `quantization`, `abliterated`, `instruction tuning`, `distillation`, `merge`, `control`) and the study groups by it.

## Outputs

| File | Contents |
| --- | --- |
| `study.md` | Tables by kind, by metric (audits, how many changed, median, smallest and largest delta), every audit, and feature, causal and scan results when those files sit next to a report |
| `study.csv` | One row per audit with every metric's delta, interval and significance, for your own analysis |
| `study.tex` | A `booktabs` table of audits ready for `\input{}` in a paper |
| `study.json` | Everything above, machine readable |

The summary reads only verified fields of each report. Run `modeldiffr registry build` on the same folder first if you want reports that fail verification left out; the registry build refuses them.

## Into the technical report

The [technical report draft](../paper.md) includes `study.tex` directly:

```latex
\input{../study/study.tex}
```
