import json

import pytest

from modeldiffr.backend import HFBackend
from modeldiffr.cli import main
from modeldiffr.interp.capture import capture
from modeldiffr.interp.crosscoder import (
    CrosscoderConfig,
    classify,
    feature_activations,
    load,
    train,
)
from modeldiffr.interp.crosscoder import save as save_xc
from modeldiffr.interp.features import verify_features
from modeldiffr.interp.layerwise import compare_layers, linear_cka
from modeldiffr.interp.model import InterpError, resolve_layers
from modeldiffr.interp.run import run_feature_diff
from tiny_models import save, sentences, torch  # noqa: F401


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    root = tmp_path_factory.mktemp("interp")
    base = save(root / "base", 0)
    same = save(root / "same", 0)
    deriv = save(root / "deriv", 0, perturb="model.layers.1.mlp.down_proj.weight", scale=0.5)
    return {
        "base": HFBackend(base, device="cpu"),
        "same": HFBackend(same, device="cpu"),
        "deriv": HFBackend(deriv, device="cpu"),
        "paths": (base, same, deriv),
    }


def test_layer_specs(models):
    m = models["base"].model
    assert resolve_layers(m, "all") == [0, 1, 2]
    assert resolve_layers(m, "middle") == [1]
    assert resolve_layers(m, "-1") == [2]
    assert resolve_layers(m, "0-1,2") == [0, 1, 2]
    with pytest.raises(InterpError):
        resolve_layers(m, "7")
    with pytest.raises(InterpError):
        resolve_layers(m, "x")


def test_linear_cka_properties():
    g = torch.Generator().manual_seed(0)
    x = torch.randn(200, 8, generator=g, dtype=torch.float64)
    q, _ = torch.linalg.qr(torch.randn(8, 8, generator=g, dtype=torch.float64))
    assert linear_cka(x, x) == pytest.approx(1.0)
    assert linear_cka(x, 3 * x @ q) == pytest.approx(1.0)
    assert linear_cka(x, torch.randn(200, 8, generator=g, dtype=torch.float64)) < 0.3


def test_identical_models_show_no_change(models):
    acts = capture(models["base"], models["same"], sentences(20), [0, 1, 2], max_tokens=2000)
    for row in compare_layers(acts):
        assert row["cka"] == pytest.approx(1.0, abs=1e-6)
        assert row["relative_change"] == pytest.approx(0.0, abs=1e-6)


def test_change_starts_at_the_perturbed_layer(models):
    acts = capture(models["base"], models["deriv"], sentences(20), [0, 1, 2], max_tokens=2000)
    rows = {r["layer"]: r for r in compare_layers(acts)}
    assert rows[0]["relative_change"] == pytest.approx(0.0, abs=1e-6)
    assert rows[1]["relative_change"] > 0.05
    assert rows[1]["cka"] < 1 - 1e-4
    assert acts.n <= 2000 and acts.texts_skipped == 0


def test_capture_respects_token_budget_and_skips_bos(models):
    acts = capture(models["base"], models["same"], sentences(50), [1], max_tokens=100)
    assert acts.n == 100
    assert all(pos >= 1 for _, pos in acts.tokens)


def synthetic(n=6000, d=16, seed=0):
    g = torch.Generator().manual_seed(seed)
    shared = torch.nn.functional.normalize(torch.randn(24, d, generator=g), dim=1)
    only_d = torch.nn.functional.normalize(torch.randn(4, d, generator=g), dim=1)
    only_b = torch.nn.functional.normalize(torch.randn(4, d, generator=g), dim=1)
    codes_s = (torch.rand(n, 24, generator=g) < 0.08).float() * (1 + torch.rand(n, 24, generator=g))
    codes_d = (torch.rand(n, 4, generator=g) < 0.08).float() * (1 + torch.rand(n, 4, generator=g))
    codes_b = (torch.rand(n, 4, generator=g) < 0.08).float() * (1 + torch.rand(n, 4, generator=g))
    xb = codes_s @ shared + codes_b @ only_b
    xd = codes_s @ shared + codes_d @ only_d
    return xb, xd, only_b, only_d


def _density(model, xb, xd):
    counts = torch.zeros(model.b_enc.shape[0])
    for _, f in feature_activations(model, xb, xd):
        counts += (f > 0).float().sum(0)
    return (counts / xb.shape[0]).tolist()


def test_crosscoder_finds_new_and_lost_directions():
    xb, xd, only_b, only_d = synthetic()
    cfg = CrosscoderConfig(dict_size=64, k=4, steps=1500, batch_size=512, lr=3e-3, seed=0)
    model, stats = train(xb, xd, cfg)
    assert stats["fve_base"] > 0.8 and stats["fve_derivative"] > 0.8
    labels, rel, cos = classify(model, _density(model, xb, xd))
    dec = model.decoders().detach()
    new = [i for i, c in enumerate(labels) if c == "derivative_only"]
    lost = [i for i, c in enumerate(labels) if c == "base_only"]
    assert new and lost
    for truth, idx, side in ((only_d, new, 1), (only_b, lost, 0)):
        found = torch.nn.functional.normalize(dec[side, idx], dim=1)
        best = (truth @ found.T).max(dim=1).values
        assert (best > 0.9).sum() >= 3


def test_crosscoder_on_identical_inputs_finds_only_shared():
    xb, _, _, _ = synthetic()
    cfg = CrosscoderConfig(dict_size=48, k=4, steps=600, batch_size=512, lr=3e-3)
    model, _ = train(xb, xb.clone(), cfg)
    labels, rel, _ = classify(model, _density(model, xb, xb))
    alive = [r for r, c in zip(rel, labels, strict=True) if c != "dead"]
    assert all(0.3 < r < 0.7 for r in alive)
    assert "derivative_only" not in labels and "base_only" not in labels


def test_delta_variant_and_save_load(tmp_path):
    xb, xd, _, only_d = synthetic()
    cfg = CrosscoderConfig(dict_size=64, k=4, steps=800, batch_size=512, lr=3e-3, variant="delta")
    model, stats = train(xb, xd, cfg)
    assert stats["fve_derivative"] > 0.6
    h = save_xc(model, tmp_path / "x.safetensors", cfg)
    assert h.startswith("sha256:")
    again, cfg2 = load(tmp_path / "x.safetensors")
    assert cfg2 == cfg
    a = next(feature_activations(model, xb[:100], xd[:100]))[1]
    b = next(feature_activations(again, xb[:100], xd[:100]))[1]
    assert torch.equal(a, b)


def test_training_is_deterministic():
    xb, xd, _, _ = synthetic(n=2000)
    cfg = CrosscoderConfig(dict_size=32, k=4, steps=50, batch_size=256, seed=3)
    a, _ = train(xb, xd, cfg)
    b, _ = train(xb, xd, cfg)
    for k, v in a.state_dict().items():
        assert torch.equal(v, b.state_dict()[k]), k


def test_feature_diff_end_to_end_and_verify(models, tmp_path):
    labels = []

    def labeler(prompt):
        labels.append(prompt)
        return "nouns after adjectives"

    cfg = CrosscoderConfig(dict_size=64, k=4, steps=200, batch_size=256, lr=3e-3)
    doc = run_feature_diff(
        models["base"],
        models["deriv"],
        sentences(80),
        "test",
        tmp_path / "f",
        layer="1",
        cfg=cfg,
        max_tokens=3000,
        per_class=3,
        n_examples=4,
        labeler=labeler,
        labeler_model="fake",
    )
    assert doc["id"].startswith("mdrf1:")
    assert sum(doc["classes"].values()) == 64
    assert doc["manifest"]["labeling"]["prompt_sha256"].startswith("sha256:")
    assert doc["features"] and all(f["label_verified"] is False for f in doc["features"])
    assert any(f["examples"] for f in doc["features"])
    ex = next(f["examples"][0] for f in doc["features"] if f["examples"])
    assert set(ex) == {"activation", "before", "token", "after"}
    assert labels and "[[" in labels[0]
    assert (tmp_path / "f" / "features.html").read_text().startswith("<!doctype html>")
    result = verify_features(tmp_path / "f" / "features.json")
    assert result["ok"], result
    assert main(["verify", str(tmp_path / "f" / "features.json")]) == 0
    p = tmp_path / "f" / "features.json"
    d = json.loads(p.read_text())
    d["classes"]["shared"] += 1
    p.write_text(json.dumps(d))
    assert not verify_features(p)["ok"]
    (tmp_path / "f" / "crosscoder.safetensors").write_bytes(b"x")
    checks = {c["name"]: c["status"] for c in verify_features(p)["checks"]}
    assert checks["crosscoder.safetensors"] == "fail"


def test_features_refuses_models_that_differ_from_the_report(models, tmp_path):
    fake_report = {
        "audit_id": "mdr1:" + "0" * 64,
        "verdict": {"changed": []},
        "manifest": {"base": {"weights_root": "sha256:" + "1" * 64}, "derivative": {}},
    }
    with pytest.raises(InterpError, match="base weights differ"):
        run_feature_diff(
            models["base"],
            models["deriv"],
            sentences(40),
            "test",
            tmp_path / "g",
            layer="1",
            cfg=CrosscoderConfig(dict_size=16, k=2, steps=5, batch_size=64),
            report=fake_report,
        )


def test_cli_layers_and_features(models, tmp_path, capsys):
    base, _, deriv = models["paths"]
    corpus = tmp_path / "c.jsonl"
    corpus.write_text("\n".join(json.dumps({"text": t}) for t in sentences(60)))
    assert main(["layers", base, deriv, "--corpus", str(corpus), "--device", "cpu"]) == 0
    out = capsys.readouterr().out
    assert "largest change at layer" in out
    code = main(
        [
            "features",
            base,
            deriv,
            "--corpus",
            str(corpus),
            "--device",
            "cpu",
            "--layer",
            "1",
            "--dict-size",
            "32",
            "--k",
            "4",
            "--steps",
            "30",
            "--batch-size",
            "128",
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    assert "features id mdrf1:" in capsys.readouterr().out
    pos = tmp_path / "p.txt"
    neg = tmp_path / "n.txt"
    pos.write_text("\n\n".join(["please the cat is safe"] * 4))
    neg.write_text("\n\n".join(["the dog runs over the road"] * 4))
    args = ["directions", base, deriv, "--positive", str(pos), "--negative", str(neg)]
    assert main(args + ["--device", "cpu", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["cosine"] == pytest.approx(1.0, abs=1e-5)
