---
title: Governance
description: Who decides what in the project, how releases are made, and how to become a maintainer.
---

# Governance

Who decides what in the project, how releases are made, and how to become a maintainer.

## Roles

| Role | Who | Can |
| --- | --- | --- |
| User | Anyone | Open issues and discussions |
| Contributor | Anyone with a merged pull request | Listed in release notes |
| Maintainer | Listed in [MAINTAINERS.md](https://github.com/amareshhebbar/modeldiffr/blob/main/MAINTAINERS.md) | Review, merge, triage, release |
| Lead maintainer | Amaresh Hebbar | Breaks ties and owns the roadmap until there are three maintainers |

## How decisions are made

| Change | Needs |
| --- | --- |
| Most code and docs | One maintainer approval and green CI |
| Proof layer: `proof`, `attest`, `anchor`, schemas, any id or hash | Two maintainer approvals |
| A published format or the [compatibility promise](reference/compatibility.md) | A `proposal` issue open seven days and a majority of maintainers |
| A claim about what Modeldiffr detects | The data and code that produced it, in the same change |

## Becoming a maintainer

Any maintainer can nominate a contributor who has reviewed and merged work over several months. The nomination passes when no maintainer objects within fourteen days. Maintainers inactive for six months become emeritus and can return by asking.

## Releases

Releases follow [RELEASING.md](https://github.com/amareshhebbar/modeldiffr/blob/main/RELEASING.md): a release pull request, a signed tag, a GitHub release that triggers trusted publishing to PyPI, and a check from a clean environment.

The full text is in [GOVERNANCE.md](https://github.com/amareshhebbar/modeldiffr/blob/main/GOVERNANCE.md).
