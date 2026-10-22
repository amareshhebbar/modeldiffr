---
title: CLI overview
description: The modeldiffr command.
---

# CLI overview

The modeldiffr command.

```text
usage: modeldiffr [-h] [--version] {audit,suites,tasks,power,refusal-eval,verify,fingerprint} ...

Audit what changed between a base LLM and a derivative model.
```

| Command | Purpose |
| --- | --- |
| [`audit`](audit.md) | Compare a base model with a derivative model |
| [`verify`](verify.md) | Check that a report was not edited and matches the real model files |
| [`fingerprint`](fingerprint.md) | Print content hashes for one model |
| [`suites`](suites.md) | List available suites |
| [`tasks`](other.md#tasks) | List tasks with their pinned datasets |
| [`power`](other.md#power) | Smallest change a task size can detect |
| [`refusal-eval`](other.md#refusal-eval) | Measure a refusal detector on labeled responses |

## Global options

#### `--version`

*flag*

Print `modeldiffr 0.3.0` and exit.

#### `-h, --help`

*flag*

Show help for the command or subcommand.

## Entry points

All three are equivalent:

```bash
modeldiffr audit base derivative
python -m modeldiffr audit base derivative
```

```python
from modeldiffr.cli import main

exit_code = main(["audit", "base", "derivative"])
```

`main` returns the exit code instead of exiting, which makes it easy to call from tests. See [exit codes](../exit_codes.md).

## Output streams

| Stream | Content |
| --- | --- |
| stderr | Progress lines prefixed with `[modeldiffr]`, and errors |
| stdout | Metric summary table, notes, and report paths |
