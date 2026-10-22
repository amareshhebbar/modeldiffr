---
title: Responsible use
description: Modeldiffr is a measurement tool.
---

# Responsible use

Modeldiffr is a measurement tool.

Modeldiffr never modifies model weights. Its reports describe **what** changed and **how much**, not how to reproduce or reverse a change.

## Disclosing findings about public models

If an audit shows that a public model has a serious safety regression or hidden behavior:

1. Rerun with pinned revisions and save the full `report.json`.
2. Contact the model's publisher privately before posting the finding.
3. Give them reasonable time to respond or update the model card.
4. When you publish, include the full report so others can reproduce it.

## Interpreting results fairly

* Report intervals, not only deltas.
* Do not describe a within noise result as a regression or an improvement.
* State the suite and its size. A result on the `quick` suite is a smoke signal, not a benchmark score.

## Security issues in Modeldiffr

For vulnerabilities in Modeldiffr itself, follow [SECURITY.md](https://github.com/amareshhebbar/modeldiffr/blob/main/SECURITY.md) rather than opening a public issue.
