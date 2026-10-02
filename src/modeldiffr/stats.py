import random
from statistics import fmean


def paired_bootstrap(
    base: list[float],
    derivative: list[float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    if len(base) != len(derivative):
        raise ValueError("base and derivative must have the same number of items")
    if not base:
        raise ValueError("at least one paired item is required")
    diffs = [d - b for b, d in zip(base, derivative, strict=True)]
    n = len(diffs)
    rng = random.Random(seed)
    means = sorted(fmean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(n_resamples))
    alpha = (1.0 - confidence) / 2.0
    low = means[int(alpha * (n_resamples - 1))]
    high = means[int((1.0 - alpha) * (n_resamples - 1))]
    return {
        "n": n,
        "base_mean": fmean(base),
        "derivative_mean": fmean(derivative),
        "delta": fmean(diffs),
        "ci_low": low,
        "ci_high": high,
        "confidence": confidence,
        "significant": low > 0.0 or high < 0.0,
    }


def one_sample_bootstrap(
    values: list[float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
    min_effect: float = 0.0,
) -> dict:
    zeros = [0.0] * len(values)
    result = paired_bootstrap(zeros, values, n_resamples, confidence, seed)
    result["min_effect"] = min_effect
    result["significant"] = result["ci_low"] > min_effect
    return result
