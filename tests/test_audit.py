from modeldiffr.audit import run_audit
from modeldiffr.suites import QUICK


def test_identical_models_show_no_change(fake_backend):
    base = fake_backend("base")
    derivative = fake_backend("derivative")
    result = run_audit(base, derivative, QUICK, n_resamples=500)
    assert result["verdict"]["any_change"] is False
    names = [m["name"] for m in result["metrics"]]
    assert names == ["capability_accuracy", "over_refusal_rate", "output_divergence_kl"]


def test_capability_drop_is_flagged(fake_backend):
    base = fake_backend("base", correct=True)
    derivative = fake_backend("derivative", correct=False)
    result = run_audit(base, derivative, QUICK, n_resamples=500)
    metric = next(m for m in result["metrics"] if m["name"] == "capability_accuracy")
    assert metric["base_mean"] == 1.0
    assert metric["derivative_mean"] == 0.0
    assert "capability_accuracy" in result["verdict"]["changed"]


def test_over_refusal_increase_is_flagged(fake_backend):
    base = fake_backend("base", refuse=False)
    derivative = fake_backend("derivative", refuse=True)
    result = run_audit(base, derivative, QUICK, n_resamples=500)
    assert "over_refusal_rate" in result["verdict"]["changed"]


def test_divergence_skipped_for_different_tokenizers(fake_backend):
    base = fake_backend("base", vocab="a")
    derivative = fake_backend("derivative", vocab="b")
    result = run_audit(base, derivative, QUICK, n_resamples=500)
    assert all(m["name"] != "output_divergence_kl" for m in result["metrics"])
    assert result["notes"]


def test_divergence_flagged_when_outputs_shift(fake_backend):
    base = fake_backend("base", kl=0.0)
    derivative = fake_backend("derivative", kl=0.3)
    result = run_audit(base, derivative, QUICK, n_resamples=500)
    assert "output_divergence_kl" in result["verdict"]["changed"]
