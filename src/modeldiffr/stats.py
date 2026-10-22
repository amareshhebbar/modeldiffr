import math
import random
from collections.abc import Callable, Sequence
from statistics import NormalDist, fmean


def _two_sided_p(samples: Sequence[float], null: float = 0.0) -> float:
    n = len(samples)
    low = sum(1 for s in samples if s <= null)
    high = sum(1 for s in samples if s >= null)
    return min(1.0, 2.0 * min(low, high) / n)


def _bounds(samples: list[float], confidence: float) -> tuple[float, float]:
    samples.sort()
    n = len(samples)
    alpha = (1.0 - confidence) / 2.0
    return samples[int(alpha * (n - 1))], samples[int((1.0 - alpha) * (n - 1))]


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
    means = [fmean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(n_resamples)]
    p_value = _two_sided_p(means)
    low, high = _bounds(means, confidence)
    return {
        "n": n,
        "base_mean": fmean(base),
        "derivative_mean": fmean(derivative),
        "delta": fmean(diffs),
        "ci_low": low,
        "ci_high": high,
        "confidence": confidence,
        "p_value": p_value,
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
    rng = random.Random(seed)
    n = len(values)
    means = [fmean(values[rng.randrange(n)] for _ in range(n)) for _ in range(n_resamples)]
    result["p_value"] = sum(1 for m in means if m <= min_effect) / n_resamples
    result["min_effect"] = min_effect
    result["significant"] = result["ci_low"] > min_effect
    return result


def paired_statistic_bootstrap(
    base_rows: list,
    derivative_rows: list,
    statistic: Callable[[list], float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    if len(base_rows) != len(derivative_rows):
        raise ValueError("base and derivative must have the same number of items")
    if not base_rows:
        raise ValueError("at least one paired item is required")
    n = len(base_rows)
    b, d = statistic(base_rows), statistic(derivative_rows)
    rng = random.Random(seed)
    deltas = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        deltas.append(
            statistic([derivative_rows[i] for i in idx]) - statistic([base_rows[i] for i in idx])
        )
    p_value = _two_sided_p(deltas)
    low, high = _bounds(deltas, confidence)
    return {
        "n": n,
        "base_mean": b,
        "derivative_mean": d,
        "delta": d - b,
        "ci_low": low,
        "ci_high": high,
        "confidence": confidence,
        "p_value": p_value,
        "significant": low > 0.0 or high < 0.0,
    }


def expected_calibration_error(rows: list[dict], bins: int = 10) -> float:
    if not rows:
        return 0.0
    buckets: list[list[dict]] = [[] for _ in range(bins)]
    for r in rows:
        c = min(max(float(r["confidence"]), 0.0), 1.0)
        buckets[min(int(c * bins), bins - 1)].append(r)
    total = len(rows)
    ece = 0.0
    for bucket in buckets:
        if bucket:
            acc = fmean(float(r["correct"]) for r in bucket)
            conf = fmean(float(r["confidence"]) for r in bucket)
            ece += len(bucket) / total * abs(acc - conf)
    return ece


def benjamini_hochberg(p_values: list[float], q: float = 0.05) -> list[bool]:
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    cutoff = -1
    for rank, i in enumerate(order, start=1):
        if p_values[i] <= q * rank / m:
            cutoff = rank
    keep = set(order[:cutoff]) if cutoff > 0 else set()
    return [i in keep for i in range(m)]


def min_detectable_effect(
    n: int, base_rate: float = 0.5, alpha: float = 0.05, power: float = 0.8, rho: float = 0.5
) -> float:
    if n <= 0:
        return math.inf
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    p = min(max(base_rate, 1e-6), 1 - 1e-6)
    var = 2 * p * (1 - p) * (1 - rho)
    return z * math.sqrt(var / n)
