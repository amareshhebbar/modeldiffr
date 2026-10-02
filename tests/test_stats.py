import pytest

from modeldiffr.stats import one_sample_bootstrap, paired_bootstrap


def test_identical_inputs_are_not_significant():
    values = [1.0, 0.0, 1.0, 1.0, 0.0] * 4
    result = paired_bootstrap(values, values, seed=1)
    assert result["delta"] == 0.0
    assert result["significant"] is False


def test_clear_drop_is_significant():
    base = [1.0] * 30
    derivative = [0.0] * 30
    result = paired_bootstrap(base, derivative, seed=1)
    assert result["delta"] == -1.0
    assert result["significant"] is True
    assert result["ci_high"] < 0


def test_bootstrap_is_deterministic_for_a_seed():
    base = [1.0, 0.0, 1.0, 0.0, 1.0, 1.0]
    derivative = [0.0, 0.0, 1.0, 1.0, 0.0, 1.0]
    assert paired_bootstrap(base, derivative, seed=7) == paired_bootstrap(base, derivative, seed=7)


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0], [1.0, 0.0])


def test_empty_raises():
    with pytest.raises(ValueError):
        paired_bootstrap([], [])


def test_one_sample_detects_positive_shift():
    assert one_sample_bootstrap([0.5] * 10, seed=0)["significant"] is True
    assert one_sample_bootstrap([0.0] * 10, seed=0)["significant"] is False


def test_one_sample_respects_min_effect():
    tiny = [1e-6] * 10
    assert one_sample_bootstrap(tiny, seed=0, min_effect=1e-3)["significant"] is False
