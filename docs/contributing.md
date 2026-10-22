---
title: Contributing
description: How to report bugs, propose suites, and open pull requests.
---

# Contributing

How to report bugs, propose suites, and open pull requests.

Modeldiffr aims to be the open, trustworthy way to audit derivative models, and that only works with many eyes on it. Contributions are welcome, from bug reports to new evaluation suites.

## Ways to contribute

<div class="grid cards" markdown>

-   **[Report a bug](https://github.com/amareshhebbar/modeldiffr/issues/new/choose)**

    ---

    Include the exact command, model ids, and `report.json` if you can share it.

-   **[Propose a feature or suite](https://github.com/amareshhebbar/modeldiffr/issues/new/choose)**

    ---

    Open a feature request before writing large amounts of code.

-   **[Improve docs](https://github.com/amareshhebbar/modeldiffr/tree/main/docs)**

    ---

    Docs, examples, and error messages are some of the most valuable contributions.

-   **[Pick up an issue](https://github.com/amareshhebbar/modeldiffr/issues?q=is%3Aopen+label%3A%22good+first+issue%22)**

    ---

    Comment first so two people do not work on the same thing.

</div>

## Development setup

```bash
git clone https://github.com/amareshhebbar/modeldiffr.git
cd modeldiffr
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Add the `hf` extra only if you need to run real models. The unit tests use a fake backend and run without PyTorch.

```bash
pip install -e ".[hf,dev]"
```

## Before you open a pull request

```bash
ruff format src tests
ruff check src tests
pytest
```

All three must pass. CI runs the same checks on Python 3.10, 3.11, and 3.12.

## Pull request guidelines

* Keep each pull request focused on one change.
* Add or update tests for any behavior you change. New metrics need a test showing that identical models produce no significant change and that a clear change is flagged.
* Update `CHANGELOG.md` under "Unreleased".
* Update the docs if you change the CLI or the report.
* Do not commit model weights, large datasets, or generated reports. Link to them instead.

## Code style

* Formatting and linting use Ruff with the settings in `pyproject.toml` (line length 100, target Python 3.10).
* Prefer clear names over comments.
* Keep the core package free of heavy imports. Anything that needs PyTorch or Transformers belongs behind the `hf` extra and is imported lazily.

## Working on these docs

The docs live in `docs/` as Markdown and are built with MkDocs Material. The navigation is in `mkdocs.yml`.

```bash
pip install -r docs/requirements.txt
mkdocs serve
```

Open `http://127.0.0.1:8000`. Every push to `main` rebuilds the published site on Netlify. Before pushing, build in strict mode, which fails on broken links and pages missing from the navigation:

```bash
mkdocs build --strict
```

## Commit messages

Short, imperative summaries, for example `Add calibration metric` or `Fix tokenizer mismatch detection`.
