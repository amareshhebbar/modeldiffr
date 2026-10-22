from modeldiffr.proof.canonical import canonical_json
from modeldiffr.proof.merkle import leaf_hash, root_hex

SECTIONS = ("capability", "over_refusal")
KL_TOLERANCE = 1e-3


def suite_leaves_v02(suite) -> list[bytes]:
    leaves = []
    for item in suite.capability:
        leaves.append(
            {
                "kind": "capability",
                "question": item.question,
                "choices": list(item.choices),
                "answer": item.answer,
            }
        )
    for prompt in suite.benign_prompts:
        leaves.append({"kind": "over_refusal", "prompt": prompt})
    for text in suite.neutral_texts:
        leaves.append({"kind": "divergence", "text": text})
    return [leaf_hash(canonical_json(x)) for x in leaves]


def suite_root_v02(suite) -> str:
    return root_hex(suite_leaves_v02(suite))


def suite_entry_v02(suite) -> dict:
    return {
        "name": suite.name,
        "root": suite_root_v02(suite),
        "items": len(suite.capability) + len(suite.benign_prompts) + len(suite.neutral_texts),
    }


def result_leaves_v02(items: dict) -> list[bytes]:
    leaves = []
    for section in SECTIONS:
        for model in ("base", "derivative"):
            for index, row in enumerate(items[section][model]):
                record = {"section": section, "model": model, "index": index, "row": row}
                leaves.append(leaf_hash(canonical_json(record)))
    for index, row in enumerate(items.get("divergence", [])):
        record = {"section": "divergence", "model": "pair", "index": index, "row": row}
        leaves.append(leaf_hash(canonical_json(record)))
    return leaves


def results_root_v02(items: dict) -> str:
    return root_hex(result_leaves_v02(items))


def _metric(name, description, higher_is_better, stats, directional=True):
    return {
        "name": name,
        "description": description,
        "higher_is_better": higher_is_better,
        "directional": directional,
        **stats,
    }


def metrics_v02(items: dict, seed: int, n_resamples: int) -> list[dict]:
    from modeldiffr.stats import one_sample_bootstrap, paired_bootstrap

    def strip(d):
        d = dict(d)
        d.pop("p_value", None)
        return d

    cap, ref = items["capability"], items["over_refusal"]
    out = [
        _metric(
            "capability_accuracy",
            "Accuracy on built in multiple choice items, scored by log likelihood.",
            True,
            strip(
                paired_bootstrap(
                    [r["correct"] for r in cap["base"]],
                    [r["correct"] for r in cap["derivative"]],
                    n_resamples=n_resamples,
                    seed=seed,
                )
            ),
        ),
        _metric(
            "over_refusal_rate",
            "Share of benign prompts that the model refuses (keyword detector).",
            False,
            strip(
                paired_bootstrap(
                    [r["refused"] for r in ref["base"]],
                    [r["refused"] for r in ref["derivative"]],
                    n_resamples=n_resamples,
                    seed=seed,
                )
            ),
        ),
    ]
    if items.get("divergence"):
        out.append(
            _metric(
                "output_divergence_kl",
                "Mean KL divergence of next token distributions on neutral text.",
                False,
                strip(
                    one_sample_bootstrap(
                        [r["kl"] for r in items["divergence"]],
                        n_resamples=n_resamples,
                        seed=seed,
                        min_effect=KL_TOLERANCE,
                    )
                ),
                directional=False,
            )
        )
    return out
