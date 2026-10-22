from dataclasses import asdict, dataclass

from modeldiffr.stats import (
    benjamini_hochberg,
    expected_calibration_error,
    one_sample_bootstrap,
    paired_bootstrap,
    paired_statistic_bootstrap,
)

FDR_Q = 0.05


@dataclass(frozen=True)
class MetricSpec:
    name: str
    description: str
    task: str
    field: str = "score"
    statistic: str = "mean"
    test: str = "paired"
    higher_is_better: bool = True
    directional: bool = True
    min_effect: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _stat(spec: dict, rows_base, rows_deriv, rows_pair, seed: int, n_resamples: int) -> dict:
    if spec["test"] == "one_sample":
        values = [float(r[spec["field"]]) for r in rows_pair]
        return one_sample_bootstrap(
            values, n_resamples=n_resamples, seed=seed, min_effect=spec["min_effect"]
        )
    if spec["statistic"] == "ece":
        return paired_statistic_bootstrap(
            rows_base, rows_deriv, expected_calibration_error, n_resamples=n_resamples, seed=seed
        )
    return paired_bootstrap(
        [float(r[spec["field"]]) for r in rows_base],
        [float(r[spec["field"]]) for r in rows_deriv],
        n_resamples=n_resamples,
        seed=seed,
    )


def compute_metrics(
    items: dict, specs: list[dict], seed: int, n_resamples: int, q: float = FDR_Q
) -> list[dict]:
    out = []
    for spec in specs:
        block = items.get(spec["task"]) or {}
        base, deriv, pair = (
            block.get("base", []),
            block.get("derivative", []),
            block.get("pair", []),
        )
        if spec["test"] == "one_sample":
            if not pair:
                continue
        elif not base or not deriv:
            continue
        stats = _stat(spec, base, deriv, pair, seed, n_resamples)
        out.append(
            {
                "name": spec["name"],
                "description": spec["description"],
                "higher_is_better": spec["higher_is_better"],
                "directional": spec["directional"],
                "spec": dict(spec),
                **stats,
            }
        )
    keep = benjamini_hochberg([m["p_value"] for m in out], q)
    for m, k in zip(out, keep, strict=True):
        m["significant_raw"] = m["significant"]
        m["significant"] = bool(m["significant_raw"] and k)
        m["negligible"] = bool(
            m["significant"]
            and m["spec"]["test"] == "paired"
            and abs(m["delta"]) < m["spec"]["min_effect"]
        )
    return out


def verdict(metrics: list[dict]) -> dict:
    changed = [m["name"] for m in metrics if m["significant"] and not m["negligible"]]
    negligible = [m["name"] for m in metrics if m["negligible"]]
    return {"changed": changed, "negligible": negligible, "any_change": bool(changed)}
