---
title: Exit codes
description: What each exit code from modeldiffr means.
---

# Exit codes

What each exit code from modeldiffr means.

| Code | Command | Meaning |
| --- | --- | --- |
| `0` | any | Success. For `audit`, the reports were written. Without `--fail-on-change`, `0` is returned even when metrics changed. |
| `1` | `audit` | `--fail-on-change` was set and `verdict.any_change` is true. Reports are still written. |
| `2` | any | Missing dependency, unsupported weight format, an unreadable report, a signing or anchoring error, or `sign` without `--key` or `--sigstore`. Also returned by argparse on invalid arguments. |
| `3` | `audit` | The pair cannot be compared fairly, for example `--template base` with different tokenizers. Nothing was run. |
| `4` | `verify`, `reveal` | At least one verification check failed, or a revealed file does not match its commitment. |

Other failures, such as a model id that does not exist or running out of GPU memory, raise the underlying exception with a non zero exit and a traceback.

## Shell usage

```bash
modeldiffr audit org/base ./candidate --fail-on-change --out audit
case $? in
  0) echo "no significant change" ;;
  1) echo "changed, see audit/report.html" ; exit 1 ;;
  *) echo "audit did not run" ; exit 2 ;;
esac
```
