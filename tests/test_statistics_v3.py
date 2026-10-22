import copy
import json
from pathlib import Path

import pytest

from modeldiffr.metrics import compute_metrics, verdict
from modeldiffr.proof.verify import verify_report
from modeldiffr.stats import (
    benjamini_hochberg,
    expected_calibration_error,
    min_detectable_effect,
    paired_bootstrap,
    paired_statistic_bootstrap,
)

DATA = Path(__file__).parent / "data"


def test_p_values():
    same = paired_bootstrap([1.0, 0.0] * 20, [1.0, 0.0] * 20, seed=1)
    assert same["p_value"] == 1.0
    drop = paired_bootstrap([1.0] * 40, [0.0] * 40, seed=1)
    assert drop["p_value"] == 0.0 and drop["significant"]


def test_benjamini_hochberg_matches_hand_example():
    p = [0.01, 0.04, 0.03, 0.005, 0.2]
    assert benjamini_hochberg(p, 0.05) == [True, True, True, True, False]
    assert benjamini_hochberg([0.04, 0.05], 0.05) == [True, True]
    assert benjamini_hochberg([0.03, 0.2, 0.3], 0.05) == [False, False, False]
    assert benjamini_hochberg([]) == []


def test_ece():
    perfect = [{"confidence": 1.0, "correct": 1.0}] * 10 + [
        {"confidence": 0.0, "correct": 0.0}
    ] * 10
    assert expected_calibration_error(perfect) == 0
    over = [{"confidence": 0.9, "correct": 0.0}] * 10
    assert abs(expected_calibration_error(over) - 0.9) < 1e-12
    r = paired_statistic_bootstrap(perfect, over * 2, expected_calibration_error, n_resamples=200)
    assert r["delta"] > 0.8 and r["significant"]


def test_min_detectable_effect_shrinks_with_n():
    assert min_detectable_effect(100) > min_detectable_effect(1000) > 0
    assert abs(min_detectable_effect(500, 0.6) - 0.0614) < 0.001


def _spec(name, task, min_effect=0.0):
    return {
        "name": name,
        "description": "",
        "task": task,
        "field": "score",
        "statistic": "mean",
        "test": "paired",
        "higher_is_better": True,
        "directional": True,
        "min_effect": min_effect,
    }


def test_correction_and_negligible():
    n = 2000
    base = [{"score": 1.0}] * n
    small = [{"score": 0.0}] * 10 + [{"score": 1.0}] * (n - 10)
    items = {"a": {"base": base, "derivative": small}, "b": {"base": base, "derivative": base}}
    ms = compute_metrics(
        items, [_spec("a_acc", "a", min_effect=0.01), _spec("b_acc", "b")], seed=0, n_resamples=500
    )
    a = ms[0]
    assert a["significant_raw"] and a["significant"] and a["negligible"]
    v = verdict(ms)
    assert v == {"changed": [], "negligible": ["a_acc"], "any_change": False}


def test_report_v02_still_verifies():
    report = json.loads((DATA / "report_v02.json").read_text())
    res = verify_report(report)
    assert res["ok"], [c for c in res["checks"] if c["status"] != "pass"]
    tampered = copy.deepcopy(report)
    tampered["items"]["capability"]["base"][0]["correct"] = 0.0
    assert not verify_report(tampered)["ok"]


def test_unknown_schema_is_refused():
    report = json.loads((DATA / "report_v02.json").read_text())
    report["schema_version"] = "9.9"
    pytest.importorskip("jsonschema")
    res = verify_report(report)
    assert not res["ok"] and "not supported" in res["checks"][0]["detail"]
