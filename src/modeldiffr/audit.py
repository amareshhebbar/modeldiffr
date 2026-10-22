import platform
import time
from collections.abc import Callable
from datetime import datetime, timezone

from modeldiffr.checks import ComparabilityError, check_pair, resolve_template_mode
from modeldiffr.proof.canonical import sha256_hex
from modeldiffr.proof.manifest import (
    audit_id as compute_audit_id,
)
from modeldiffr.proof.manifest import (
    build_manifest,
    results_root,
    statement_hash,
    suite_root,
)
from modeldiffr.refusal import is_refusal
from modeldiffr.stats import one_sample_bootstrap, paired_bootstrap
from modeldiffr.suites import Suite

SCHEMA_VERSION = "0.2"
PROOF_ALGORITHMS = {
    "canonical_json": "RFC 8785",
    "hash": "SHA-256",
    "merkle": "RFC 6962",
    "audit_id": "mdr1 = sha256(canonical(manifest))",
}
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


def _text_hash(text: str | None) -> str | None:
    return None if text is None else "sha256:" + sha256_hex(text.encode("utf-8"))


def _refusal_scores(backend, suite: Suite, renderer=None) -> list[dict]:
    rows = []
    for prompt in suite.benign_prompts:
        rendered = None
        if renderer is not None and hasattr(backend, "generate_raw"):
            rendered = renderer.render_chat(prompt)
            text = backend.generate_raw(rendered, suite.max_new_tokens)
        else:
            if hasattr(backend, "render_chat"):
                rendered = backend.render_chat(prompt)
            text = backend.generate(prompt, suite.max_new_tokens)
        rows.append(
            {
                "prompt": prompt,
                "rendered_sha256": _text_hash(rendered),
                "response": text,
                "refused": float(is_refusal(text)),
            }
        )
    return rows


def _fingerprint(backend, weights: bool, progress) -> tuple[dict | None, list[str]]:
    if not hasattr(backend, "fingerprint"):
        return None, []
    from modeldiffr.fingerprint import UnsupportedWeightsError

    try:
        return backend.fingerprint(weights=weights), []
    except UnsupportedWeightsError as exc:
        progress(f"weights not fingerprinted for {backend.name}: {exc}")
        fp = backend.fingerprint(weights=False)
        return fp, [f"Weights of {backend.name} were not fingerprinted: {exc}"]


def _renderer(mode: str, base, derivative):
    pick = {"base": base, "derivative": derivative}.get(mode)
    if pick is None or not hasattr(pick, "render_chat"):
        return None
    return pick


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


def metrics_from_items(items: dict, seed: int, n_resamples: int) -> list[dict]:
    cap, ref = items["capability"], items["over_refusal"]
    metrics = [
        _metric(
            "capability_accuracy",
            "Accuracy on built in multiple choice items, scored by log likelihood.",
            True,
            paired_bootstrap(
                [r["correct"] for r in cap["base"]],
                [r["correct"] for r in cap["derivative"]],
                n_resamples=n_resamples,
                seed=seed,
            ),
        ),
        _metric(
            "over_refusal_rate",
            "Share of benign prompts that the model refuses (keyword detector).",
            False,
            paired_bootstrap(
                [r["refused"] for r in ref["base"]],
                [r["refused"] for r in ref["derivative"]],
                n_resamples=n_resamples,
                seed=seed,
            ),
        ),
    ]
    if items.get("divergence"):
        metrics.append(
            _metric(
                "output_divergence_kl",
                "Mean KL divergence of next token distributions on neutral text.",
                False,
                one_sample_bootstrap(
                    [r["kl"] for r in items["divergence"]],
                    n_resamples=n_resamples,
                    seed=seed,
                    min_effect=KL_TOLERANCE,
                ),
                directional=False,
            )
        )
    return metrics


def run_audit(
    base,
    derivative,
    suite: Suite,
    seed: int = 0,
    n_resamples: int = 2000,
    progress: ProgressFn = _noop,
    template: str = "auto",
    hash_weights: bool = True,
) -> dict:
    from modeldiffr import __version__
    from modeldiffr.fingerprint import diff_weights

    started = time.perf_counter()
    notes: list[str] = []

    progress("fingerprinting base" + (" weights and tokenizer" if hash_weights else " tokenizer"))
    base_fp, n1 = _fingerprint(base, hash_weights, progress)
    progress("fingerprinting derivative")
    derivative_fp, n2 = _fingerprint(derivative, hash_weights, progress)
    notes += n1 + n2
    template_mode = resolve_template_mode(template, base_fp, derivative_fp)
    base_meta, derivative_meta = base.metadata(), derivative.metadata()
    comparability = check_pair(base_fp, derivative_fp, base_meta, derivative_meta, template_mode)
    if not comparability["ok"]:
        raise ComparabilityError(comparability["issues"])
    settings = {
        "seed": seed,
        "n_resamples": n_resamples,
        "max_new_tokens": suite.max_new_tokens,
        "decoding": "greedy",
        "template_mode": template_mode,
        "weights_hashed": hash_weights,
    }
    manifest = build_manifest(
        base_meta, base_fp, derivative_meta, derivative_fp, suite, settings, __version__
    )
    audit_id = compute_audit_id(manifest)
    progress(f"audit id {audit_id}")

    progress("capability: scoring base")
    base_cap = _capability_scores(base, suite)
    progress("capability: scoring derivative")
    deriv_cap = _capability_scores(derivative, suite)

    progress("over refusal: generating with base")
    renderer = _renderer(template_mode, base, derivative)
    base_ref = _refusal_scores(base, suite, renderer)
    progress("over refusal: generating with derivative")
    deriv_ref = _refusal_scores(derivative, suite, renderer)

    divergence_rows = []
    divergence_note = None
    if base.vocab_signature() == derivative.vocab_signature():
        progress("output divergence: computing KL on neutral text")
        for text in suite.neutral_texts:
            divergence_rows.append({"text": text, "kl": base.divergence_to(derivative, text)})
    else:
        divergence_note = "Skipped output divergence: the two models use different tokenizers."

    items = {
        "capability": {"base": base_cap, "derivative": deriv_cap},
        "over_refusal": {"base": base_ref, "derivative": deriv_ref},
        "divergence": divergence_rows,
    }
    metrics = metrics_from_items(items, seed=seed, n_resamples=n_resamples)
    changed = [m["name"] for m in metrics if m["significant"]]
    weights_diff = None
    bw = (base_fp or {}).get("weights") or {}
    dw = (derivative_fp or {}).get("weights") or {}
    if bw.get("leaves") is not None and dw.get("leaves") is not None:
        weights_diff = diff_weights(bw["leaves"], dw["leaves"])

    result = {
        "schema_version": SCHEMA_VERSION,
        "modeldiffr_version": __version__,
        "audit_id": audit_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "suite": {
            "name": suite.name,
            "root": manifest["suite"]["root"],
            "notes": list(suite.notes),
        },
        "settings": settings,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "base": base_meta,
        "derivative": derivative_meta,
        "manifest": manifest,
        "fingerprints": {"base": base_fp, "derivative": derivative_fp},
        "comparability": comparability,
        "weights_diff": weights_diff,
        "metrics": metrics,
        "verdict": {"changed": changed, "any_change": bool(changed)},
        "notes": notes + [n for n in [divergence_note] if n],
        "items": items,
        "proof": {
            "algorithms": dict(PROOF_ALGORITHMS),
            "audit_id": audit_id,
            "suite_root": suite_root(suite),
            "results_root": results_root(items),
        },
        "wall_time_seconds": round(time.perf_counter() - started, 2),
    }
    result["proof"]["statement_sha256"] = statement_hash(result)
    return result
