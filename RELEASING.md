# Releasing

Releases are cut from `main` by a maintainer.

## Checklist

1. Make sure `main` is green in CI.
2. Update the version in `pyproject.toml`, `src/modeldiffr/__init__.py`, `CITATION.cff` and the BibTeX entry in `README.md`.
3. Move the `Unreleased` entries in `CHANGELOG.md` under the new version with the date, and add the same entry to `docs/changelog.md`.
4. If a format changed, update [Schemas and compatibility](docs/reference/compatibility.md) and add a test that a file from the previous version still verifies.
5. Run the full checks locally:

    ```bash
    pip install -e ".[dev]"
    ruff format --check src tests && ruff check src tests
    pytest
    pip install -r docs/requirements.txt && mkdocs build --strict
    python -m build && twine check --strict dist/*
    ```

6. Open a pull request named `Release X.Y.Z`, merge it after review.
7. Tag and push:

    ```bash
    git checkout main && git pull
    git tag -a vX.Y.Z -m "Modeldiffr X.Y.Z"
    git push origin vX.Y.Z
    ```

8. Create the GitHub release from the tag with the changelog entry as its notes:

    ```bash
    gh release create vX.Y.Z --title "Modeldiffr X.Y.Z" --notes-file notes.md
    ```

    Publishing the release starts the publish workflow, which checks that the tag matches the package version, builds, and uploads to PyPI.

9. Check that `pip install modeldiffr==X.Y.Z` works in a clean environment and that the documentation site shows the new version.

## Version numbers

Semantic Versioning. Before 1.0, a minor release may change formats; the changelog must say how and older reports must keep verifying. From 1.0 the [compatibility promise](docs/reference/compatibility.md) applies.

## Security fixes

Security fixes follow [SECURITY.md](SECURITY.md): a private advisory first, a patch release, then disclosure.
