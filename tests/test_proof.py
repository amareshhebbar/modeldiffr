import copy
import json

import pytest

from modeldiffr.audit import run_audit
from modeldiffr.checks import ComparabilityError
from modeldiffr.cli import main
from modeldiffr.proof.verify import verify_report
from modeldiffr.report import write_reports
from modeldiffr.suites import QUICK


@pytest.fixture
def report(fp_backend):
    base = fp_backend("base")
    deriv = fp_backend(
        "deriv",
        correct=False,
        leaves={"layer.0.weight": "a" * 64, "layer.1.weight": "c" * 64, "extra": "d" * 64},
    )
    return run_audit(base, deriv, QUICK, n_resamples=300)


def statuses(result):
    return {c["name"]: c["status"] for c in result["checks"]}


def test_report_verifies_after_a_json_round_trip(report, tmp_path):
    path, _ = write_reports(report, tmp_path)
    loaded = json.loads(path.read_text())
    result = verify_report(loaded)
    assert result["ok"], result
    s = statuses(result)
    assert s["schema"] == "pass" and s["suite"] == "pass" and s["weights_diff"] == "pass"
    assert loaded["weights_diff"]["changed"] == ["layer.1.weight"]
    assert loaded["weights_diff"]["added"] == ["extra"]


def test_audit_id_depends_only_on_inputs(fp_backend):
    a = run_audit(fp_backend("base"), fp_backend("d"), QUICK, n_resamples=100)
    b = run_audit(fp_backend("base"), fp_backend("d"), QUICK, n_resamples=100)
    assert a["audit_id"] == b["audit_id"]
    c = run_audit(fp_backend("base"), fp_backend("d"), QUICK, n_resamples=100, seed=1)
    assert c["audit_id"] != a["audit_id"]
    other = fp_backend("d", leaves={"layer.0.weight": "e" * 64})
    assert run_audit(fp_backend("base"), other, QUICK, n_resamples=100)["audit_id"] != a["audit_id"]


@pytest.mark.parametrize(
    "edit,failing",
    [
        (
            lambda r: r["items"]["capability"]["base"][0].update(correct=0.0),
            {"results_root", "metrics"},
        ),
        (lambda r: r["metrics"][0].update(delta=0.5), {"metrics", "statement"}),
        (lambda r: r["verdict"].update(changed=[], any_change=False), {"verdict", "statement"}),
        (
            lambda r: r["manifest"]["derivative"].update(weights_root="sha256:" + "0" * 64),
            {"audit_id", "manifest_consistency"},
        ),
        (lambda r: r["settings"].update(seed=9), {"manifest_consistency"}),
        (
            lambda r: r["fingerprints"]["base"]["weights"]["leaves"].update(
                {"layer.0.weight": "f" * 64}
            ),
            {"base_weights_leaves"},
        ),
        (lambda r: r["proof"].update(suite_root="sha256:" + "1" * 64), {"suite"}),
        (lambda r: r["weights_diff"].update(changed_count=0), {"weights_diff", "statement"}),
    ],
)
def test_tampering_is_detected(report, edit, failing):
    tampered = copy.deepcopy(json.loads(json.dumps(report)))
    edit(tampered)
    result = verify_report(tampered)
    assert not result["ok"]
    failed = {n for n, s in statuses(result).items() if s == "fail"}
    assert failing <= failed, failed


def test_missing_field_fails_schema(report):
    broken = json.loads(json.dumps(report))
    del broken["proof"]
    result = verify_report(broken)
    assert not result["ok"] and result["checks"][0]["name"] == "schema"


def test_self_audit_control_fifty_seeds(fp_backend):
    for seed in range(50):
        r = run_audit(fp_backend("m"), fp_backend("m"), QUICK, n_resamples=200, seed=seed)
        assert r["verdict"]["any_change"] is False, seed
        assert r["weights_diff"]["identical"]
        assert any(i["code"] == "weights_identical" for i in r["comparability"]["issues"])


def test_shared_template_renders_identical_prompts(fp_backend):
    r = run_audit(
        fp_backend("b", template="A"), fp_backend("d", template="B"), QUICK, n_resamples=100
    )
    assert r["settings"]["template_mode"] == "base"
    b = [x["rendered_sha256"] for x in r["items"]["over_refusal"]["base"]]
    d = [x["rendered_sha256"] for x in r["items"]["over_refusal"]["derivative"]]
    assert b == d and all(b)
    own = run_audit(
        fp_backend("b", template="A"),
        fp_backend("d", template="B"),
        QUICK,
        n_resamples=100,
        template="own",
    )
    assert (
        own["items"]["over_refusal"]["base"][0]["rendered_sha256"]
        != own["items"]["over_refusal"]["derivative"][0]["rendered_sha256"]
    )


def test_shared_template_with_different_vocab_is_refused(fp_backend):
    class OtherVocab(fp_backend):
        def fingerprint(self, weights=True):
            fp = super().fingerprint(weights)
            fp["tokenizer"]["vocab"] = "sha256:" + "2" * 64
            return fp

    with pytest.raises(ComparabilityError):
        run_audit(
            fp_backend("b", template="A"), OtherVocab("d", template="B"), QUICK, template="base"
        )


def test_cli_verify_exit_codes(report, tmp_path, capsys):
    path, _ = write_reports(report, tmp_path)
    assert main(["verify", str(path)]) == 0
    assert "verified" in capsys.readouterr().out
    data = json.loads(path.read_text())
    data["metrics"][0]["ci_low"] = -9.0
    path.write_text(json.dumps(data))
    assert main(["verify", str(path), "--json"]) == 4
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert main(["verify", str(tmp_path / "missing.json")]) == 2


def test_backends_without_fingerprints_still_verify(fake_backend):
    r = run_audit(fake_backend("a"), fake_backend("b"), QUICK, n_resamples=100)
    assert r["fingerprints"] == {"base": None, "derivative": None}
    assert verify_report(json.loads(json.dumps(r)))["ok"]
