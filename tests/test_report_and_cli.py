import json

import pytest

from modeldiffr import __version__
from modeldiffr.audit import run_audit
from modeldiffr.cli import main
from modeldiffr.report import write_reports
from modeldiffr.suites import QUICK, get_suite


def test_reports_are_written(tmp_path, fake_backend):
    result = run_audit(fake_backend("a"), fake_backend("b", correct=False), QUICK, n_resamples=200)
    json_path, html_path = write_reports(result, tmp_path / "out")
    data = json.loads(json_path.read_text())
    assert data["schema_version"] == "0.1"
    assert data["modeldiffr_version"] == __version__
    page = html_path.read_text()
    assert "<!doctype html>" in page
    assert "capability_accuracy" in page
    assert "regressed" in page


def test_html_escapes_model_names(tmp_path, fake_backend):
    result = run_audit(
        fake_backend("<script>x</script>"), fake_backend("b"), QUICK, n_resamples=200
    )
    _, html_path = write_reports(result, tmp_path)
    assert "<script>x</script>" not in html_path.read_text()


def test_cli_suites(capsys):
    assert main(["suites"]) == 0
    assert "quick" in capsys.readouterr().out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_suite_raises():
    with pytest.raises(KeyError):
        get_suite("missing")


def test_divergence_is_labelled_changed_not_regressed(tmp_path, fake_backend):
    result = run_audit(fake_backend("a", kl=0.0), fake_backend("b", kl=0.5), QUICK, n_resamples=200)
    _, html_path = write_reports(result, tmp_path)
    page = html_path.read_text()
    assert "moved" in page
    assert "regressed" not in page
