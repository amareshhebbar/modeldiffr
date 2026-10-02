import platform
import time
from collections.abc import Callable
from datetime import datetime, timezone

from modeldiffr.refusal import is_refusal
from modeldiffr.stats import one_sample_bootstrap, paired_bootstrap
from modeldiffr.suites import Suite

SCHEMA_VERSION = "0.1"
KL_TOLERANCE = 1e-3

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:
    return None


def _format_question(question: str) -> str:
    return f"Question: {question}\nAnswer:"


def _capability_scores(backend, suite: Suite) -> list[dict]:
    rows = []
    for item in suite.capability:
        prompt = _format_question(item.question)
        scores = [backend.choice_logprob(prompt, " " + choice) for choice in item.choices]
        predicted = max(range(len(scores)), key=scores.__getitem__)
        rows.append(
            {
                "question": item.question,
                "predicted": item.choices[predicted],
                "expected": item.choices[item.answer],
                "correct": float(predicted == item.answer),
            }
        )
    return rows


def _refusal_scores(backend, suite: Suite) -> list[dict]:
    rows = []
    for prompt in suite.benign_prompts:
        text = backend.generate(prompt, suite.max_new_tokens)
        rows.append({"prompt": prompt, "response": text, "refused": float(is_refusal(text))})
    return rows


def _metric(
    name: str, description: str, higher_is_better: bool, stats: dict, directional: bool = True
) -> dict:
    return {
        "name": name,
        "description": description,
        "higher_is_better": higher_is_better,
        "directional": directional,
        **stats,
    }


def run_audit(
    base,
    derivative,
    suite: Suite,
    seed: int = 0,
    n_resamples: int = 2000,
    progress: ProgressFn = _noop,
) -> dict:
    from modeldiffr import __version__

    started = time.perf_counter()

    progress("capability: scoring base")
    base_cap = _capability_scores(base, suite)
    progress("capability: scoring derivative")
    deriv_cap = _capability_scores(derivative, suite)

    progress("over refusal: generating with base")
    base_ref = _refusal_scores(base, suite)
    progress("over refusal: generating with derivative")
    deriv_ref = _refusal_scores(derivative, suite)

    metrics = [
        _metric(
            "capability_accuracy",
            "Accuracy on built in multiple choice items, scored by log likelihood.",
            True,
            paired_bootstrap(
                [r["correct"] for r in base_cap],
                [r["correct"] for r in deriv_cap],
                n_resamples=n_resamples,
                seed=seed,
            ),
        ),
        _metric(
            "over_refusal_rate",
            "Share of benign prompts that the model refuses (keyword detector).",
            False,
            paired_bootstrap(
                [r["refused"] for r in base_ref],
                [r["refused"] for r in deriv_ref],
                n_resamples=n_resamples,
                seed=seed,
            ),
        ),
    ]

    divergence_rows = []
    divergence_note = None
    if base.vocab_signature() == derivative.vocab_signature():
        progress("output divergence: computing KL on neutral text")
        for text in suite.neutral_texts:
            divergence_rows.append({"text": text, "kl": base.divergence_to(derivative, text)})
        metrics.append(
            _metric(
                "output_divergence_kl",
                "Mean KL divergence of next token distributions on neutral text.",
                False,
                one_sample_bootstrap(
                    [r["kl"] for r in divergence_rows],
                    n_resamples=n_resamples,
                    seed=seed,
                    min_effect=KL_TOLERANCE,
                ),
                directional=False,
            )
        )
    else:
        divergence_note = "Skipped output divergence: the two models use different tokenizers."

    changed = [m["name"] for m in metrics if m["significant"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "modeldiffr_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "suite": {"name": suite.name, "notes": list(suite.notes)},
        "settings": {
            "seed": seed,
            "n_resamples": n_resamples,
            "max_new_tokens": suite.max_new_tokens,
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "base": base.metadata(),
        "derivative": derivative.metadata(),
        "metrics": metrics,
        "verdict": {"changed": changed, "any_change": bool(changed)},
        "notes": [n for n in [divergence_note] if n],
        "items": {
            "capability": {"base": base_cap, "derivative": deriv_cap},
            "over_refusal": {"base": base_ref, "derivative": deriv_ref},
            "divergence": divergence_rows,
        },
        "wall_time_seconds": round(time.perf_counter() - started, 2),
    }
