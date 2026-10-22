import csv
import io
import json

import pytest

from modeldiffr.batch import run_batch
from modeldiffr.cli import main
from modeldiffr.study import StudyError, collect, metric_table, to_latex, write_study
from test_publish import fake_runner, write_spec


@pytest.fixture
def audits(tmp_path, fp_backend):
    spec = write_spec(
        tmp_path,
        [
            {"name": "quant_a", "base": "m", "derivative": "m-q4", "kind": "quantization"},
            {"name": "ft_b", "base": "m", "derivative": "m-bad", "kind": "fine tune"},
            {"name": "ft_c", "base": "m", "derivative": "m-bad-2", "kind": "fine tune"},
        ],
    )
    run_batch(spec, runner=fake_runner(fp_backend))
    root = tmp_path / "audits"
    (root / "ft_b" / "features.json").write_text(
        json.dumps(
            {
                "manifest": {"layer": 7},
                "classes": {
                    "shared": 9,
                    "shifted": 2,
                    "base_only": 1,
                    "derivative_only": 3,
                    "dead": 0,
                },
            }
        )
    )
    (root / "ft_b" / "causal.json").write_text(
        json.dumps(
            {
                "manifest": {"layer": 7},
                "conditions": [{"share": 0.62, "explainable": True, "share_ci": [0.4, 0.8]}],
            }
        )
    )
    (root / "ft_b" / "scan.json").write_text(
        json.dumps({"flagged": True, "summary": {"outliers": 2}})
    )
    return root


def test_collect_reads_kinds_and_side_files(audits):
    rows = collect([audits])
    by = {r["name"]: r for r in rows}
    assert by["quant_a"]["kind"] == "quantization"
    assert by["ft_b"]["kind"] == "fine tune"
    assert by["ft_b"]["changed"] and not by["quant_a"]["changed"]
    assert by["ft_b"]["features"]["derivative_only"] == 3
    assert by["ft_b"]["causal"]["patch_layer_share"] == 0.62
    assert by["ft_b"]["scan"]["flagged"] is True
    table = {m["metric"]: m for m in metric_table(rows)}
    assert table["capability_accuracy"]["audits"] == 3
    assert table["capability_accuracy"]["changed"] == 2


def test_outputs(audits, tmp_path):
    data = write_study([audits], tmp_path / "study")
    out = tmp_path / "study"
    rows = list(csv.DictReader(io.StringIO((out / "study.csv").read_text())))
    assert len(rows) == 3 and "capability_accuracy_delta" in rows[0]
    md = (out / "study.md").read_text()
    assert "## By kind of derivative" in md and "| fine tune | 2 | 2 |" in md
    assert "## Inside the models" in md and "62%" in md and "flagged" in md
    tex = (out / "study.tex").read_text()
    assert r"quant\_a" in tex and r"\toprule" in tex
    assert json.loads((out / "study.json").read_text())["schema"] == "modeldiffr.study/1"
    assert {k["kind"] for k in data["by_kind"]} == {"quantization", "fine tune"}


def test_latex_escaping():
    rows = [{"name": "a_b&c%", "kind": None, "suite": "x#y", "changed": ["m_1"]}]
    tex = to_latex(rows)
    assert r"a\_b\&c\%" in tex and r"x\#y" in tex and r"m\_1" in tex


def test_study_cli_and_errors(audits, tmp_path, capsys):
    assert main(["study", str(audits), "--out", str(tmp_path / "s")]) == 0
    assert "3 audits, 2 with a significant change" in capsys.readouterr().out
    (tmp_path / "empty").mkdir()
    with pytest.raises(StudyError):
        collect([tmp_path / "empty"])
