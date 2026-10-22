# Governance

Modeldiffr is an open source project under the Apache 2.0 license. This document says who decides what, and how that changes as the project grows.

## Roles

**Users** run Modeldiffr and report problems. Anyone can open an issue or a discussion.

**Contributors** have had a pull request merged. They are listed in the release notes.

**Maintainers** review and merge pull requests, triage issues, and cut releases. They are listed in [MAINTAINERS.md](MAINTAINERS.md).

**The lead maintainer** breaks ties and owns the roadmap until the project has three or more maintainers, after which the roadmap is decided by the maintainers together.

## Decisions

* Most changes are decided in the pull request: one maintainer approval and passing CI, or two approvals for changes to the proof layer (`modeldiffr/proof`, `modeldiffr/attest`, the report schema, any id or hash definition).
* Changes to a published format or to the compatibility promise need a written proposal as an issue labeled `proposal`, open for at least seven days, and approval from a majority of maintainers.
* Claims about what Modeldiffr detects, such as backdoor detection rates, are only added to documentation together with the data and code that produced them.

## Becoming a maintainer

Contributors who have reviewed and merged work over several months, and who show care for correctness and for users, can be nominated by any maintainer. A nomination is accepted when no maintainer objects within fourteen days. Maintainers who are inactive for six months move to emeritus status and can return by asking.

## Conflicts of interest

Maintainers disclose employment or funding related to a model they audit in public, and do not merge their own changes to the proof layer.

## Code of conduct

Everyone in the project follows the [Code of Conduct](CODE_OF_CONDUCT.md). Reports go to the address listed there.

## Changes to this document

Changes follow the proposal process above.
