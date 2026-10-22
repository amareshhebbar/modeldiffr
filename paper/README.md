# Technical report

LaTeX source for the Modeldiffr technical report. The methods are written; the results come from published audits.

## Build

```bash
modeldiffr batch ../examples/public_audits.yaml --out ../audits
modeldiffr study ../audits --out ../study
latexmk -pdf main.tex
```

`main.tex` includes `../study/study.tex` when it exists and prints a placeholder otherwise, so the draft always compiles.

## Rules

* Every number in the report comes from a file written by Modeldiffr and published, signed, in the registry.
* Results that are not run yet are marked as pending, never estimated.
