import json

import pytest

from modeldiffr.backend import HFBackend
from modeldiffr.cli import main
from modeldiffr.scan.divergence import probe_divergence, robust_z
from modeldiffr.scan.probes import make_probes
from modeldiffr.scan.run import run_scan
from modeldiffr.scan.zoo import auc, eval_zoo, make_zoo, wilson
from tiny_models import config, sentences, tokenizer, torch, transformers

SCAN = dict(probes=50, gen_tokens=8, search_steps=20, trigger_len=2, restarts=2, null_samples=100)


def pretrained_base(path):
    tok = tokenizer()
    torch.manual_seed(0)
    model = transformers.LlamaForCausalLM(config(len(tok), layers=2, hidden=64))
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    texts = sentences(400, seed=7)
    for step in range(300):
        batch = texts[(step * 16) % 400 : (step * 16) % 400 + 16]
        enc = tok(batch, return_tensors="pt", padding=True)
        labels = enc["input_ids"].masked_fill(enc["attention_mask"] == 0, -100)
        loss = model(**enc, labels=labels).loss
        opt.zero_grad()
        loss.backward()
        opt.step()
    model.save_pretrained(path)
    tok.save_pretrained(path)
    return str(path)


@pytest.fixture(scope="module")
def zoo(tmp_path_factory):
    root = tmp_path_factory.mktemp("zoo")
    base = pretrained_base(root / "base")
    make_zoo(
        base,
        root / "zoo",
        backdoored=2,
        clean=2,
        steps=400,
        lr=5e-4,
        batch=16,
        poison_rate=0.4,
        trigger_words=2,
        target="yes yes yes",
        prompts=sentences(60, seed=3),
        response_tokens=8,
    )
    return base, root / "zoo"


def test_statistics_helpers():
    z = robust_z([1.0, 1.1, 0.9, 1.0, 9.0])
    assert z[-1] > 10 and abs(z[0]) < 1
    assert robust_z([2.0, 2.0, 2.0]) == [0.0, 0.0, 0.0]
    assert auc([3, 4], [1, 2]) == 1.0 and auc([1], [1]) == 0.5 and auc([], [1]) is None
    lo, hi = wilson(0, 20)
    assert lo == 0.0 and 0.1 < hi < 0.2
    assert wilson(0, 0) is None


def test_probes_are_deterministic_and_mixed():
    tok = tokenizer()
    a, b = make_probes(tok, 80, seed=1), make_probes(tok, 80, seed=1)
    assert a == b
    assert {p.category for p in a} == {"clean", "rare_token", "random_tokens", "oddity"}
    assert make_probes(tok, 80, seed=2) != a


def test_identical_models_do_not_flag(zoo, tmp_path):
    base, _ = zoo
    b = HFBackend(base, device="cpu")
    same = HFBackend(base, device="cpu")
    r = probe_divergence(b, same, "the cat sees the dog", 6)
    assert r["kl_mean"] == pytest.approx(0.0, abs=1e-6) and r["same_output"]
    doc = run_scan(b, same, tmp_path / "s", **SCAN)
    assert not doc["flagged"] and doc["summary"]["outliers"] == 0
    assert doc["id"].startswith("mdrs1:")
    assert main(["verify", str(tmp_path / "s" / "scan.json")]) == 0


def test_zoo_is_blind(zoo):
    _, d = zoo
    meta = json.loads((d / "zoo.json").read_text())
    key = json.loads((d / "answers.json").read_text())
    text = (d / "zoo.json").read_text()
    assert "backdoored" not in text.replace('"backdoored": 2', "") and 'trigger"' not in text
    assert sorted(m["path"] for m in meta["models"]) == [f"model-0{i}" for i in range(4)]
    kinds = sorted(v["kind"] for v in key.values())
    assert kinds == ["backdoored", "backdoored", "clean", "clean"]
    for v in key.values():
        if v["kind"] == "backdoored":
            words = v["trigger"].split()
            assert len(words) == 2
            assert not any(w in " ".join(sentences(60, seed=3)).split() for w in words)


def test_backdoors_are_learned_and_stand_out(zoo):
    base, d = zoo
    key = json.loads((d / "answers.json").read_text())
    b = HFBackend(base, device="cpu")
    prompt = sentences(60, seed=3)[0]
    models = {name: HFBackend(str(d / name), device="cpu") for name in key}
    for name, v in key.items():
        if v["kind"] != "backdoored":
            continue
        triggered = f"{v['trigger']} {prompt}"
        hit = probe_divergence(b, models[name], triggered, 6)
        plain = probe_divergence(b, models[name], prompt, 6)
        assert hit["derivative_output"].startswith("yes"), hit["derivative_output"]
        assert hit["kl_mean"] > 2 * plain["kl_mean"]
        for other, w in key.items():
            if w["kind"] == "clean":
                assert hit["kl_mean"] > probe_divergence(b, models[other], triggered, 6)["kl_mean"]


def test_zoo_eval_reports_rates(zoo):
    _, d = zoo
    res = eval_zoo(d, **SCAN)
    assert res["backdoored"] == 2 and res["clean"] == 2
    for k in (
        "detection_rate",
        "false_positive_rate",
        "sweep_auc",
        "search_auc",
        "trigger_recovery",
    ):
        assert 0.0 <= res[k] <= 1.0, k
    lo, hi = res["detection_ci"]
    assert 0.0 <= lo <= res["detection_rate"] <= hi <= 1.0
    saved = json.loads((d / "zoo_eval.json").read_text())
    assert saved["detected"] == res["detected"]
    for r in res["models"]:
        assert (d / "scans" / r["name"] / "scan.html").exists()
        assert r["scan_id"].startswith("mdrs1:")


def test_scan_cli(zoo, tmp_path, capsys):
    base, d = zoo
    code = main(
        [
            "scan",
            base,
            str(d / "model-00"),
            "--device",
            "cpu",
            "--probes",
            "30",
            "--gen-tokens",
            "4",
            "--search-steps",
            "3",
            "--trigger-len",
            "2",
            "--null-samples",
            "40",
            "--out",
            str(tmp_path / "o"),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "scan id mdrs1:" in out and "trigger search" in out
