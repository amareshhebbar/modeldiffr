import json

import pytest

from modeldiffr.backend import HFBackend
from modeldiffr.cli import main
from modeldiffr.interp.causal import Patcher, mc_items, share_explained
from modeldiffr.interp.causal_run import run_causal
from modeldiffr.interp.crosscoder import CrosscoderConfig
from modeldiffr.interp.run import run_feature_diff
from modeldiffr.tasks.base import Item
from modeldiffr.tasks.multiple_choice import MultipleChoiceTask
from tiny_models import save, sentences, torch  # noqa: F401

NOUNS = ["dog", "bird", "fish", "tree"]


class NounTask(MultipleChoiceTask):
    name = "nouns"

    def __init__(self):
        pass

    def prompt(self, it):
        return it.data["prompt"]

    def continuations(self, it):
        return [" " + n for n in NOUNS]

    def entry(self, items):
        return {"name": self.name, "kind": "multiple_choice", "items": len(items)}


def noun_items(n=40):
    import random

    rng = random.Random(1)
    out = []
    for i in range(n):
        words = ["the", rng.choice(["red", "small", "old"]), rng.choice(NOUNS), "sees", "the"]
        out.append(Item(str(i), {"prompt": " ".join(words), "answer": i % 4}))
    return out


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    root = tmp_path_factory.mktemp("causal")
    base = save(root / "base", 0)
    deriv = save(root / "deriv", 0, perturb="model.layers.1.mlp.down_proj.weight", scale=3.0)
    return HFBackend(base, device="cpu"), HFBackend(deriv, device="cpu"), (base, deriv)


@pytest.fixture(scope="module")
def loaded(models):
    base, deriv, _ = models
    task = NounTask()
    items = noun_items()
    patcher = Patcher(base, deriv, 0)
    for it in items:
        mc = mc_items([(task, [it])])[0]
        gains = []
        for k in range(len(NOUNS)):
            mc.answer = k
            gains.append(
                patcher.score(mc, {"kind": "derivative"}) - patcher.score(mc, {"kind": "base"})
            )
        it.data["answer"] = max(range(len(NOUNS)), key=gains.__getitem__)
    return [(task, items)]


def test_share_explained_math():
    base = [0.2, 0.3, 0.4, 0.5]
    deriv = [0.6, 0.7, 0.8, 0.9]
    half = [0.4, 0.5, 0.6, 0.7]
    r = share_explained(base, deriv, half, n_resamples=500)
    assert r["share"] == pytest.approx(0.5)
    assert r["explainable"] and r["share_ci"][0] == pytest.approx(0.5)
    none = share_explained(base, base, half, n_resamples=200)
    assert none["share"] is None and not none["explainable"] and none["share_ci"] is None


def test_mc_items_from_tasks(loaded):
    items = mc_items(loaded)
    assert len(items) == 40 and items[0].continuations[0] == " dog"
    from modeldiffr.audit import load_items
    from modeldiffr.tasks.registry import task_suite

    quick = mc_items(load_items(task_suite("quick")))
    assert quick and all(len(i.continuations) >= 2 for i in quick)


def test_patching_the_last_layer_reproduces_the_whole_change(models, loaded):
    base, deriv, _ = models
    items = mc_items(loaded)
    last = Patcher(base, deriv, 2)
    first = Patcher(base, deriv, 0)
    for it in items[:8]:
        pb = last.score(it, {"kind": "base"})
        pd = last.score(it, {"kind": "derivative"})
        assert last.score(it, {"kind": "patch_layer"}) == pytest.approx(pd, abs=1e-5)
        assert last.score(it, {"kind": "reverse_layer"}) == pytest.approx(pb, abs=1e-5)
        assert first.score(it, {"kind": "patch_layer"}) == pytest.approx(pb, abs=1e-5)
        zero = torch.zeros(base.model.config.hidden_size)
        assert last.score(it, {"kind": "steer", "vector": zero, "alpha": 1.0}) == pytest.approx(
            pb, abs=1e-6
        )


def test_run_causal_end_to_end(models, loaded, tmp_path):
    base, deriv, _ = models
    doc = run_causal(base, deriv, loaded, "nouns", tmp_path / "c", layer="2", n_resamples=300)
    by = {r["name"]: r for r in doc["conditions"]}
    assert doc["id"].startswith("mdrc1:")
    first = by["patch_layer"]
    assert first["explainable"], first
    assert first["share"] == pytest.approx(1.0, abs=1e-4)
    assert by["reverse_layer"]["share"] == pytest.approx(1.0, abs=1e-4)
    assert {"steer_0.5", "steer_1", "steer_2"} <= set(by)
    assert (tmp_path / "c" / "causal.html").read_text().startswith("<!doctype html>")
    assert main(["verify", str(tmp_path / "c" / "causal.json")]) == 0
    p = tmp_path / "c" / "causal.json"
    d = json.loads(p.read_text())
    d["conditions"][0]["share"] = 0.1
    p.write_text(json.dumps(d))
    assert main(["verify", str(p)]) == 4


def test_layer_before_the_change_explains_nothing(models, loaded, tmp_path):
    base, deriv, _ = models
    doc = run_causal(
        base, deriv, loaded, "nouns", tmp_path / "z", layer="0", n_resamples=300, alphas=()
    )
    first = doc["conditions"][0]
    assert first["share"] == pytest.approx(0.0, abs=1e-4)


def test_feature_patching_with_a_crosscoder(models, loaded, tmp_path):
    base, deriv, _ = models
    cfg = CrosscoderConfig(dict_size=64, k=8, steps=300, batch_size=256, lr=3e-3)
    run_feature_diff(
        base, deriv, sentences(120), "test", tmp_path / "f", layer="2", cfg=cfg, max_tokens=4000
    )
    doc = run_causal(
        base,
        deriv,
        loaded,
        "nouns",
        tmp_path / "c",
        layer="2",
        features_dir=tmp_path / "f",
        top=(5, 64),
        alphas=(1.0,),
        n_resamples=300,
    )
    names = [r["name"] for r in doc["conditions"]]
    assert "patch_top_5" in names
    assert doc["manifest"]["crosscoder"].startswith("sha256:")
    assert doc["manifest"]["features_id"].startswith("mdrf1:")
    assert (
        doc["top_features"]
        and doc["top_features"][0]["attribution"] >= doc["top_features"][-1]["attribution"]
    )
    with pytest.raises(Exception, match="trained on layer 2"):
        run_causal(
            base, deriv, loaded, "nouns", tmp_path / "x", layer="1", features_dir=tmp_path / "f"
        )


def test_causal_cli(models, tmp_path, capsys):
    _, _, (b, d) = models
    code = main(
        [
            "causal",
            b,
            d,
            "--device",
            "cpu",
            "--layer",
            "-1",
            "--suite",
            "quick",
            "--limit",
            "6",
            "--resamples",
            "200",
            "--alphas",
            "1",
            "--out",
            str(tmp_path / "o"),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "causal id mdrc1:" in out and "patch_layer" in out
