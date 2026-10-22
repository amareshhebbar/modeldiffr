import platform
import time
from collections.abc import Callable
from datetime import datetime, timezone

from modeldiffr.checks import ComparabilityError, check_pair, resolve_template_mode
from modeldiffr.metrics import FDR_Q, compute_metrics, verdict
from modeldiffr.proof.manifest import (
    audit_id as compute_audit_id,
)
from modeldiffr.proof.manifest import (
    build_manifest,
    results_root,
    statement_hash,
    suite_entry,
)
from modeldiffr.stats import min_detectable_effect
from modeldiffr.suites import Suite
from modeldiffr.tasks.base import RunContext, select
from modeldiffr.tasks.registry import TaskSuite

SCHEMA_VERSION = "0.3"
KL_TOLERANCE = 1e-3
PROOF_ALGORITHMS = {
    "canonical_json": "RFC 8785",
    "hash": "SHA-256",
    "merkle": "RFC 6962",
    "audit_id": "mdr1 = sha256(canonical(manifest))",
}

ProgressFn = Callable[[str], None]


class AuditPlanError(RuntimeError):
    pass


def _noop(_: str) -> None:
    return None


def as_task_suite(suite) -> TaskSuite:
    if isinstance(suite, TaskSuite):
        return suite
    if isinstance(suite, Suite):
        from modeldiffr.tasks.builtin import legacy_tasks

        return TaskSuite(suite.name, [(t, None) for t in legacy_tasks(suite)], tuple(suite.notes))
    raise TypeError("suite must be a Suite or a TaskSuite")


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


def _context_limit(base, derivative) -> int | None:
    limits = [b.max_context() for b in (base, derivative) if hasattr(b, "max_context")]
    limits = [x for x in limits if x]
    return min(limits) if limits else None


def load_items(suite: TaskSuite, data_dir=None, context: int | None = None, progress=_noop):
    loaded = []
    for task, size in suite.entries:
        progress(f"loading {task.name}")
        items = task.load(data_dir)
        if task.name == "needle" and context:
            items = [it for it in items if it.data["words"] * 1.6 + 64 < context]
        loaded.append((task, select(task.name, items, size)))
    return loaded


def plan(loaded) -> list[dict]:
    out = []
    for task, items in loaded:
        cost = task.cost(len(items))
        paired = [m for m in task.metrics if m.test == "paired" and m.statistic == "mean"]
        out.append(
            {
                "task": task.name,
                "items": len(items),
                "loglik_calls": cost["loglik"],
                "generations": cost["generate"],
                "max_new_tokens": cost["tokens"],
                "min_detectable_effect": round(min_detectable_effect(len(items)), 4)
                if paired and items
                else None,
            }
        )
    return out


def _probe(backend) -> tuple[float, float]:
    t0 = time.perf_counter()
    for _ in range(2):
        backend.choice_logprob("The capital of France is", " Paris")
    t_ll = (time.perf_counter() - t0) / 2
    t0 = time.perf_counter()
    if hasattr(backend, "generate_raw"):
        backend.generate_raw("Count: one, two, three,", 16)
    else:
        backend.generate("Count to five.", 16)
    t_tok = (time.perf_counter() - t0) / 16
    return t_ll, t_tok


def estimate_seconds(base, derivative, rows: list[dict]) -> float:
    total = 0.0
    for backend in (base, derivative):
        t_ll, t_tok = _probe(backend)
        for r in rows:
            total += r["loglik_calls"] * t_ll + r["max_new_tokens"] * t_tok
    return total


def run_audit(
    base,
    derivative,
    suite,
    seed: int = 0,
    n_resamples: int = 2000,
    progress: ProgressFn = _noop,
    template: str = "auto",
    hash_weights: bool = True,
    refusal_detector=None,
    allow_code_execution: bool = False,
    data_dir=None,
    fdr_q: float = FDR_Q,
    estimate: bool = False,
) -> dict:
    from modeldiffr import __version__
    from modeldiffr.fingerprint import diff_weights

    started = time.perf_counter()
    suite = as_task_suite(suite)
    allow_code_execution = allow_code_execution or suite.allow_code_execution
    notes: list[str] = list(suite.notes)

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

    context_limit = _context_limit(base, derivative)
    loaded = load_items(suite, data_dir, context_limit, progress)
    if not any(items for _, items in loaded):
        raise AuditPlanError("the suite selected no items")
    detector_name = getattr(refusal_detector, "name", "keyword")
    settings = {
        "seed": seed,
        "n_resamples": n_resamples,
        "decoding": "greedy",
        "template_mode": template_mode,
        "weights_hashed": hash_weights,
        "refusal_detector": detector_name,
        "allow_code_execution": allow_code_execution,
        "fdr_q": fdr_q,
        "context_limit": context_limit,
    }
    suite_info = suite_entry(suite.name, loaded)
    manifest = build_manifest(
        base_meta, base_fp, derivative_meta, derivative_fp, suite_info, settings, __version__
    )
    audit_id = compute_audit_id(manifest)
    progress(f"audit id {audit_id}")
    plan_rows = plan(loaded)
    for row in plan_rows:
        mde = row["min_detectable_effect"]
        extra = f", detects changes of about {mde * 100:.1f} points" if mde else ""
        progress(f"plan {row['task']}: {row['items']} items{extra}")
    estimate_s = estimate_seconds(base, derivative, plan_rows) if estimate else None
    if estimate_s is not None:
        progress(f"estimated run time {estimate_s / 60:.1f} minutes on this hardware")

    ctx = RunContext(
        renderer=_renderer(template_mode, base, derivative),
        refusal_detector=refusal_detector,
        allow_code_execution=allow_code_execution,
        progress=progress,
    )
    items_out: dict = {}
    specs: list[dict] = []
    for task, items in loaded:
        if not items:
            continue
        if task.kind == "divergence":
            if not task.comparable(base, derivative):
                notes.append("Skipped output divergence: the two models use different tokenizers.")
                continue
            progress(f"{task.name}: comparing next token distributions")
            items_out[task.name] = {"pair": task.run_pair(base, derivative, items, ctx)}
        else:
            progress(f"{task.name}: base ({len(items)} items)")
            b = task.run(base, items, ctx)
            progress(f"{task.name}: derivative")
            d = task.run(derivative, items, ctx)
            items_out[task.name] = {"base": b, "derivative": d}
        specs += [m.to_dict() for m in task.metrics]

    metrics = compute_metrics(items_out, specs, seed=seed, n_resamples=n_resamples, q=fdr_q)
    weights_diff = None
    bw = (base_fp or {}).get("weights") or {}
    dw = (derivative_fp or {}).get("weights") or {}
    if bw.get("leaves") is not None and dw.get("leaves") is not None:
        formats = {bw.get("format"), dw.get("format")}
        if len(formats) == 1 or formats <= {"safetensors", "pytorch"}:
            weights_diff = diff_weights(bw["leaves"], dw["leaves"])
        else:
            notes.append("Weights are in different formats, so no tensor level diff was computed.")

    result = {
        "schema_version": SCHEMA_VERSION,
        "modeldiffr_version": __version__,
        "audit_id": audit_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "suite": {"name": suite.name, "root": suite_info["root"], "notes": list(suite.notes)},
        "settings": settings,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "base": base_meta,
        "derivative": derivative_meta,
        "manifest": manifest,
        "fingerprints": {"base": base_fp, "derivative": derivative_fp},
        "comparability": comparability,
        "weights_diff": weights_diff,
        "plan": {"tasks": plan_rows, "estimated_seconds": estimate_s},
        "metrics": metrics,
        "verdict": verdict(metrics),
        "notes": notes,
        "items": items_out,
        "proof": {
            "algorithms": dict(PROOF_ALGORITHMS),
            "audit_id": audit_id,
            "suite_root": suite_info["root"],
            "results_root": results_root(items_out),
        },
        "wall_time_seconds": round(time.perf_counter() - started, 2),
    }
    result["proof"]["statement_sha256"] = statement_hash(result)
    return result


def metrics_from_items(
    items: dict, specs: list[dict], seed: int, n_resamples: int, q: float = FDR_Q
):
    return compute_metrics(items, specs, seed=seed, n_resamples=n_resamples, q=q)
