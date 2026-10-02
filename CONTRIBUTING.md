# Contributing to Modeldiffr

Thank you for helping. Modeldiffr aims to be the open, trustworthy way to audit derivative models, and that only works with many eyes on it.

## Ways to contribute

* **Report a bug** with the bug report template. Include the exact command, model ids, and the `report.json` if you can share it.
* **Propose a feature or suite** with the feature request template before writing large amounts of code, so we can agree on the design first.
* **Improve documentation**, examples, and error messages. These are some of the most valuable contributions.
* **Pick up an issue** labelled `good first issue` or `help wanted`. Comment on it first so two people do not work on the same thing.
* **Share audit results** of public models. Real reports help everyone calibrate what normal looks like.

## Development setup

```bash
git clone https://github.com/amareshhebbar/modeldiffr.git
cd modeldiffr
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Add the `hf` extra (`pip install -e ".[hf,dev]"`) only if you need to run real models. The unit tests use a fake backend and run without PyTorch.

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
* Update the README if you change the CLI or the report.
* Do not commit model weights, large datasets, or generated reports. Link to them instead.

## Code style

* Formatting and linting are handled by Ruff with the settings in `pyproject.toml`.
* Prefer clear names over comments.
* Keep the core package free of heavy imports. Anything that needs PyTorch or Transformers belongs behind the `hf` extra and is imported lazily.

## Adding an evaluation suite

1. Define the items in `src/modeldiffr/suites.py`, or load them from an established public benchmark with its license respected and credited.
2. Register the suite in `SUITES`.
3. Add tests with the fake backend.
4. Document what the suite measures and its known weaknesses in the README.

Suites must measure behavior. Modeldiffr does not accept contributions whose purpose is to remove safety behavior from models, and suites must not include content whose main use would be causing harm.

## Commit messages

Use short, imperative summaries, for example `Add calibration metric` or `Fix tokenizer mismatch detection`.

## Licensing of contributions

By submitting a contribution, you agree that it is licensed under the [Apache License 2.0](LICENSE), the same license as the project.

## Code of conduct

Everyone taking part in this project is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions

Open a discussion or an issue, or email hebbar.gvamaresh@gmail.com.
