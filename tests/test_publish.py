import json
import shutil
import subprocess
from pathlib import Path

import pytest

from modeldiffr.audit import run_audit
from modeldiffr.batch import BatchError, outcome, run_batch, summarize
from modeldiffr.cli import main
from modeldiffr.proof.canonical import canonical_json
from modeldiffr.registry import build_registry
from modeldiffr.report import write_reports
from modeldiffr.suites import QUICK

VERIFY_JS = Path(__file__).parent.parent / "src/modeldiffr/registry/static/verify.js"
NODE = shutil.which("node")


def fake_runner(fp_backend):
    def run(argv):
        assert argv[0] == "audit"
        base, deriv = argv[1], argv[2]
        out = argv[argv.index("--out") + 1]
        changed = "bad" in deriv or "noise" in deriv
        report = run_audit(
            fp_backend(base), fp_backend(deriv, correct=not changed), QUICK, n_resamples=200
        )
        write_reports(report, out)
        return 1 if report["verdict"]["any_change"] else 0

    return run


def write_spec(tmp_path, audits, defaults=None, name="spec.json"):
    p = tmp_path / name
    data = {"out": str(tmp_path / "audits"), "defaults": defaults or {}, "audits": audits}
    if name.endswith(".yaml"):
        import yaml

        p.write_text(yaml.safe_dump(data))
    else:
        p.write_text(json.dumps(data))
    return p


def test_outcomes_and_summary():
    yes = {"any_change": True}
    no = {"any_change": False}
    assert outcome("change", yes) == "detected"
    assert outcome("change", no) == "missed"
    assert outcome("no_change", yes) == "false_positive"
    assert outcome("no_change", no) == "clean"
    assert outcome(None, yes) is None
    rows = [
        {"status": "done", "expect": "change", "outcome": "detected"},
        {"status": "done", "expect": "change", "outcome": "missed"},
        {"status": "done", "expect": "no_change", "outcome": "clean"},
        {"status": "failed", "expect": "change", "outcome": None},
    ]
    s = summarize(rows)
    assert s["detection_rate"] == 0.5 and s["false_positive_rate"] == 0.0
    assert s["failed"] == 1 and s["completed"] == 3


def test_batch_runs_scores_and_resumes(tmp_path, fp_backend):
    spec = write_spec(
        tmp_path,
        [
            {"name": "same", "base": "m", "derivative": "m-copy", "expect": "no_change"},
            {"name": "broken", "base": "m", "derivative": "m-bad", "expect": "change"},
            {"name": "plain", "base": "m", "derivative": "m-ft"},
        ],
        defaults={"suite": "quick", "seed": 3, "args": ["--resamples", "200"]},
    )
    calls = []
    runner = fake_runner(fp_backend)

    def counting(argv):
        calls.append(argv)
        return runner(argv)

    index = run_batch(spec, runner=counting)
    assert [r["status"] for r in index["audits"]] == ["done", "done", "done"]
    assert [r["outcome"] for r in index["audits"]] == ["clean", "detected", None]
    assert index["summary"]["detection_rate"] == 1.0
    assert "--seed" in calls[0] and calls[0][calls[0].index("--seed") + 1] == "3"
    assert calls[0][-2:] == ["--resamples", "200"]
    saved = json.loads((tmp_path / "audits" / "index.json").read_text())
    assert saved["audits"][1]["audit_id"].startswith("mdr1:")
    again = run_batch(spec, runner=counting)
    assert len(calls) == 3
    assert {r["status"] for r in again["audits"]} == {"existing"}


def test_batch_only_and_dry_run(tmp_path):
    spec = write_spec(
        tmp_path,
        [
            {"name": "a", "base": "x", "derivative": "y"},
            {"name": "b", "base": "x", "derivative": "z"},
        ],
    )
    index = run_batch(spec, only=["b"], dry_run=True, runner=lambda argv: 0)
    assert [r["name"] for r in index["audits"]] == ["b"]
    assert index["audits"][0]["command"].startswith("modeldiffr audit x z --out")
    assert not (tmp_path / "audits").exists()
    with pytest.raises(BatchError):
        run_batch(spec, only=["nope"], dry_run=True)


@pytest.mark.parametrize(
    "audits, message",
    [
        ([{"base": "x", "derivative": "y"}], "needs a name"),
        ([{"name": "a", "derivative": "y"}], "needs a base"),
        ([{"name": "a", "base": "x"}], "needs a derivative"),
        ([{"name": "a", "base": "x", "derivative": "y"}] * 2, "used twice"),
        ([{"name": "a b", "base": "x", "derivative": "y"}], "needs a name"),
    ],
)
def test_batch_rejects_bad_specs(tmp_path, audits, message):
    with pytest.raises(BatchError, match=message):
        run_batch(write_spec(tmp_path, audits), dry_run=True)


def test_batch_makes_controls_and_reads_yaml(tmp_path, fp_backend):
    pytest.importorskip("yaml")
    made = []

    def fake_make(base, out, **kw):
        made.append((base, out, kw))
        Path(out).mkdir(parents=True)
        Path(out, "modeldiffr_control.json").write_text("{}")

    spec = write_spec(
        tmp_path,
        [
            {"name": "noise", "base": "m", "control": {"kind": "noise", "strength": 0.2}},
            {"name": "ident", "base": "m", "control": {"kind": "identity"}},
        ],
        name="spec.yaml",
    )
    index = run_batch(spec, runner=fake_runner(fp_backend), make_control=fake_make)
    assert [r["expect"] for r in index["audits"]] == ["change", "no_change"]
    assert made[0][2]["kind"] == "noise" and made[0][2]["strength"] == 0.2
    assert index["audits"][0]["outcome"] == "detected"
    assert index["audits"][1]["outcome"] == "clean"


def test_batch_cli_reports_failures(tmp_path, monkeypatch, capsys):
    spec = write_spec(tmp_path, [{"name": "a", "base": "x", "derivative": "y"}])
    from modeldiffr import cli

    monkeypatch.setattr(cli, "_cmd_audit", lambda args: 2)
    assert main(["batch", str(spec)]) == 5
    out = capsys.readouterr().out
    assert "failed" in out and "0 of 1 audits complete" in out


def tiny_model(path, seed=0):
    torch = pytest.importorskip("torch")
    st = pytest.importorskip("safetensors.torch")
    g = torch.Generator().manual_seed(seed)
    tensors = {
        "model.embed_tokens.weight": torch.randn(32, 8, generator=g),
        "model.layers.0.mlp.down_proj.weight": torch.randn(8, 16, generator=g).to(torch.bfloat16),
        "model.layers.0.self_attn.q_proj.weight": torch.randn(8, 8, generator=g),
        "model.layers.0.input_layernorm.weight": torch.ones(8),
        "model.layers.1.mlp.down_proj.weight": torch.randn(8, 16, generator=g),
    }
    path.mkdir(parents=True)
    st.save_file(tensors, str(path / "model.safetensors"))
    (path / "config.json").write_text('{"model_type": "llama"}')
    (path / "tokenizer.json").write_text("{}")
    return tensors


def load(path):
    from safetensors.torch import load_file

    return load_file(str(path / "model.safetensors"))


def test_identity_control_has_the_same_weight_root(tmp_path):
    from modeldiffr.controls import make_control
    from modeldiffr.fingerprint import weights_fingerprint

    tiny_model(tmp_path / "base")
    rec = make_control(str(tmp_path / "base"), tmp_path / "copy", kind="identity")
    assert rec["expect"] == "no_change" and rec["tensors_changed"] == []
    assert (
        weights_fingerprint(tmp_path / "copy").root == weights_fingerprint(tmp_path / "base").root
    )
    assert (tmp_path / "copy" / "tokenizer.json").exists()


def test_noise_control_touches_only_matching_tensors_and_is_seeded(tmp_path):
    torch = pytest.importorskip("torch")
    from modeldiffr.controls import make_control

    base = tiny_model(tmp_path / "base")
    rec = make_control(str(tmp_path / "base"), tmp_path / "a", kind="noise", strength=0.5, seed=7)
    make_control(str(tmp_path / "base"), tmp_path / "b", kind="noise", strength=0.5, seed=7)
    a, b = load(tmp_path / "a"), load(tmp_path / "b")
    assert sorted(rec["tensors_changed"]) == [
        "model.layers.0.mlp.down_proj.weight",
        "model.layers.0.self_attn.q_proj.weight",
        "model.layers.1.mlp.down_proj.weight",
    ]
    assert torch.equal(a["model.embed_tokens.weight"], base["model.embed_tokens.weight"])
    assert a["model.layers.0.mlp.down_proj.weight"].dtype == torch.bfloat16
    for k in a:
        assert torch.equal(a[k], b[k])
    ratio = (
        a["model.layers.1.mlp.down_proj.weight"] - base["model.layers.1.mlp.down_proj.weight"]
    ).std()
    assert 0.3 < float(ratio / base["model.layers.1.mlp.down_proj.weight"].std()) < 0.7
    meta = json.loads((tmp_path / "a" / "modeldiffr_control.json").read_text())
    assert meta["kind"] == "noise" and meta["seed"] == 7 and meta["expect"] == "change"


def test_zero_prune_and_scale_controls(tmp_path):
    torch = pytest.importorskip("torch")
    from modeldiffr.controls import make_control

    base = tiny_model(tmp_path / "base")
    name = "model.layers.1.mlp.down_proj.weight"
    make_control(str(tmp_path / "base"), tmp_path / "z", kind="zero", match=r"layers\.1\.mlp")
    z = load(tmp_path / "z")
    assert torch.count_nonzero(z[name]) == 0
    assert torch.equal(
        z["model.layers.0.mlp.down_proj.weight"], base["model.layers.0.mlp.down_proj.weight"]
    )
    make_control(
        str(tmp_path / "base"), tmp_path / "p", kind="prune", strength=0.5, match=r"layers\.1"
    )
    p = load(tmp_path / "p")
    assert torch.count_nonzero(p[name]) == base[name].numel() // 2
    make_control(
        str(tmp_path / "base"), tmp_path / "s", kind="scale", strength=2.0, match=r"layers\.1"
    )
    assert torch.allclose(load(tmp_path / "s")[name], base[name] * 2)


def test_control_errors(tmp_path):
    from modeldiffr.controls import ControlError, make_control

    tiny_model(tmp_path / "base")
    with pytest.raises(ControlError, match="matched no"):
        make_control(str(tmp_path / "base"), tmp_path / "x", kind="noise", match="nothing_here")
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "f").write_text("x")
    with pytest.raises(ControlError, match="not empty"):
        make_control(str(tmp_path / "base"), tmp_path / "full")
    with pytest.raises(ControlError, match="unknown"):
        make_control(str(tmp_path / "base"), tmp_path / "y", kind="melt")
    (tmp_path / "nost").mkdir()
    with pytest.raises(ControlError, match="safetensors"):
        make_control(str(tmp_path / "nost"), tmp_path / "w")


def test_controls_cli(tmp_path, capsys):
    tiny_model(tmp_path / "base")
    code = main(
        ["controls", "make", str(tmp_path / "base"), "--out", str(tmp_path / "c"), "--kind", "zero"]
    )
    assert code == 0
    assert "should find: change" in capsys.readouterr().out


@pytest.fixture
def reports(fp_backend, tmp_path):
    paths = []
    for i, (b, d, ok) in enumerate([("qwen", "qwen-ft", False), ("llama", "llama-q4", True)]):
        r = run_audit(fp_backend(b), fp_backend(d, correct=ok), QUICK, n_resamples=200)
        p, _ = write_reports(r, tmp_path / "in" / f"a{i}")
        paths.append(p)
    return paths


def test_registry_lists_verified_reports(reports, tmp_path):
    reg = build_registry([tmp_path / "in"], tmp_path / "site", title="Acme audits")
    assert len(reg["audits"]) == 2
    site = tmp_path / "site"
    for f in ("index.html", "audit.html", "registry.css", "verify.js", "app.js", "registry.json"):
        assert (site / f).exists(), f
    assert "Acme audits" in (site / "index.html").read_text()
    a = reg["audits"][0]
    assert (site / "audits" / a["id"] / "report.json").exists()
    assert a["checks"]["results_root"] == "pass"
    assert {x["derivative"] for x in reg["audits"]} == {"qwen-ft", "llama-q4"}


def test_registry_skips_tampered_reports(reports, tmp_path, capsys):
    r = json.loads(reports[0].read_text())
    r["metrics"][0]["delta"] += 0.5
    reports[0].write_text(json.dumps(r))
    reg = build_registry([tmp_path / "in"], tmp_path / "site")
    assert len(reg["audits"]) == 1
    assert reg["skipped"][0]["failed"]
    assert main(["registry", "build", str(tmp_path / "in"), "--out", str(tmp_path / "s2")]) == 4
    assert (
        main(
            [
                "registry",
                "build",
                str(tmp_path / "in"),
                "--out",
                str(tmp_path / "s3"),
                "--allow-failed",
            ]
        )
        == 0
    )


def node(script, *args):
    if not NODE:
        pytest.skip("node is not installed")
    proc = subprocess.run(
        [NODE, "-e", script, str(VERIFY_JS), *map(str, args)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


CANONICAL_CASES = [
    {"b": 1, "a": [True, False, None], "é": "x", "A": 0.1},
    [1e21, 1e-7, 123456789.125, -0.0, 5e-324, 1.7976931348623157e308, 0.000001, 100.0],
    {"text": 'quote " backslash \\ newline \n tab \t ctrl \u0001 emoji \U0001f600 line  '},
    {"\U0001f600": 1, "￿": 2, "z": 3},
]


@pytest.mark.parametrize("value", CANONICAL_CASES)
def test_browser_canonical_json_matches_python(value, tmp_path):
    f = tmp_path / "v.json"
    f.write_text(json.dumps(value))
    got = node(
        "const v=require(process.argv[1]);"
        "const x=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
        "console.log(JSON.stringify(v.canonical(x)))",
        f,
    )
    assert got == canonical_json(value).decode("utf-8")


def test_browser_verifier_agrees_with_python(reports, tmp_path):
    script = (
        "const v=require(process.argv[1]);"
        "const r=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
        "console.log(JSON.stringify(v.verifyReport(r)))"
    )
    result = node(script, reports[0])
    assert result["ok"], result
    names = {c["name"]: c["status"] for c in result["checks"]}
    assert names["audit_id"] == names["results_root"] == names["statement"] == "pass"
    assert names["base_weights_leaves"] == "pass"
    for edit in (
        lambda r: r["items"][next(iter(r["items"]))]["base"][0].update(score=99),
        lambda r: r["manifest"]["settings"].update(seed=99),
        lambda r: r["verdict"].update(any_change=not r["verdict"]["any_change"]),
        lambda r: r["fingerprints"]["base"]["weights"]["leaves"].update(extra="0" * 64),
    ):
        r = json.loads(reports[0].read_text())
        edit(r)
        p = tmp_path / "t.json"
        p.write_text(json.dumps(r))
        assert not node(script, p)["ok"]


def test_browser_checks_ed25519_signatures(reports, tmp_path):
    pytest.importorskip("cryptography")
    from modeldiffr.attest.keys import generate

    priv, pub = generate(tmp_path / "k", "acme")
    _, other = generate(tmp_path / "k", "other")
    assert main(["sign", str(reports[0]), "--key", str(priv)]) == 0
    script = (
        "const v=require(process.argv[1]);const fs=require('fs');"
        "const r=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
        "const e=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));"
        "const keys=[{name:'acme',pem:fs.readFileSync(process.argv[4],'utf8')}];"
        "v.verifyEnvelope(e,r,keys).then(c=>console.log(JSON.stringify(c)))"
    )
    env = reports[0].parent / "report.dsse.json"
    assert node(script, reports[0], env, pub)["status"] == "pass"
    assert node(script, reports[0], env, other)["status"] == "fail"
    swapped = tmp_path / "other_report.json"
    swapped.write_text(reports[1].read_text())
    got = node(script, swapped, env, pub)
    assert got["status"] == "fail" and "audit_id" in got["detail"]
    reg = build_registry([tmp_path / "in"], tmp_path / "site", keys={"acme": str(pub)})
    assert reg["keys"][0]["name"] == "acme"
    assert any(a["signed"] for a in reg["audits"])


@pytest.mark.parametrize("name", ["public_audits.yaml", "controls.yaml"])
def test_example_specs_are_valid(name, tmp_path):
    pytest.importorskip("yaml")
    spec = Path(__file__).parent.parent / "examples" / name
    index = run_batch(spec, out=tmp_path, dry_run=True, runner=lambda argv: 0)
    assert len(index["audits"]) >= 10
    assert all(r["command"].startswith("modeldiffr audit ") for r in index["audits"])
