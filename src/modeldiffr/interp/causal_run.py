from pathlib import Path

from modeldiffr.interp.artifact import file_hash, finalize, now, write
from modeldiffr.interp.causal import SCHEMA, Patcher, mc_items, share_explained
from modeldiffr.interp.model import InterpError, resolve_layers, unwrap


def _items_root(loaded) -> str:
    from modeldiffr.proof.manifest import suite_root

    return suite_root(loaded)


def run_causal(
    base,
    derivative,
    loaded,
    suite_name: str,
    out: str | Path,
    layer="middle",
    features_dir: str | Path | None = None,
    top=(10, 50, 200),
    alphas=(0.5, 1.0, 2.0),
    n_resamples: int = 2000,
    seed: int = 0,
    report: dict | None = None,
    hash_weights: bool = True,
    progress=lambda _: None,
) -> dict:
    import json

    from modeldiffr import __version__
    from modeldiffr.interp.run import model_entry_for

    model, _ = unwrap(base)
    chosen = resolve_layers(model, layer)
    if len(chosen) != 1:
        raise InterpError("causal checks run on one layer; pass --layer N")
    li = chosen[0]
    items = mc_items(loaded)
    if not items:
        raise InterpError("causal checks need multiple choice tasks, such as quick, mmlu or arc")
    crosscoder, features_doc, files = None, None, {}
    if features_dir:
        from modeldiffr.interp.crosscoder import load

        fd = Path(features_dir)
        features_doc = json.loads((fd / "features.json").read_text(encoding="utf-8"))
        if features_doc["manifest"]["layer"] != li:
            raise InterpError(
                f"the crosscoder was trained on layer {features_doc['manifest']['layer']}, not {li}"
            )
        crosscoder, _ = load(fd / "crosscoder.safetensors")
        want = features_doc["files"]["crosscoder.safetensors"]
        if file_hash(fd / "crosscoder.safetensors") != want:
            raise InterpError("crosscoder.safetensors does not match features.json")
    patcher = Patcher(base, derivative, li, crosscoder)

    def scores(condition, label):
        progress(f"{label}: {len(items)} items")
        return [patcher.score(it, condition) for it in items]

    p_base = scores({"kind": "base"}, "base")
    p_deriv = scores({"kind": "derivative"}, "derivative")
    results = []

    def add(name, condition, description, reverse=False):
        cond = scores(condition, name)
        if reverse:
            stats = share_explained(p_deriv, p_base, cond, n_resamples, seed)
        else:
            stats = share_explained(p_base, p_deriv, cond, n_resamples, seed)
        results.append(
            {"name": name, "description": description, "mean": sum(cond) / len(cond), **stats}
        )

    add(
        "patch_layer",
        {"kind": "patch_layer"},
        f"Base model with its layer {li} output replaced by the derivative's",
    )
    add(
        "reverse_layer",
        {"kind": "reverse_layer"},
        f"Derivative with its layer {li} output replaced by the base's",
        reverse=True,
    )
    ranked = []
    if crosscoder is not None:
        from modeldiffr.interp.crosscoder import classify

        progress("ranking crosscoder features on task tokens")
        attr, density = patcher.attributions(items)
        labels, _, _ = classify(crosscoder, density)
        order = sorted(range(len(attr)), key=lambda i: -attr[i])
        ranked = [
            {"index": i, "attribution": round(attr[i], 6), "class": labels[i]}
            for i in order[: max(top) if top else 0]
            if attr[i] > 0
        ]
        for n in top:
            chosen_f = [r["index"] for r in ranked[:n]]
            if not chosen_f:
                continue
            add(
                f"patch_top_{n}",
                {"kind": "patch_features", "features": chosen_f},
                f"Base with the derivative's version of its top {len(chosen_f)} features",
            )
        changed = [
            i for i, c in enumerate(labels) if c in ("derivative_only", "base_only", "shifted")
        ]
        if changed:
            add(
                "patch_changed_classes",
                {"kind": "patch_features", "features": changed},
                f"Base with the derivative's version of all {len(changed)} new, lost "
                "and shifted features",
            )
    progress("computing the steering vector")
    vector = patcher.mean_difference(items)
    for a in alphas:
        add(
            f"steer_{a:g}",
            {"kind": "steer", "vector": vector, "alpha": a},
            f"Base plus {a:g} times the mean activation difference at layer {li}",
        )
    for r in results:
        for k in ("behavior_delta", "moved", "share", "mean"):
            if r.get(k) is not None:
                r[k] = round(r[k], 6)
        for k in ("behavior_ci", "share_ci"):
            if r.get(k):
                r[k] = [round(x, 6) for x in r[k]]
    if crosscoder is not None:
        files_src = Path(features_dir) / "crosscoder.safetensors"
        files = {"crosscoder.safetensors": file_hash(files_src)}
    base_entry = model_entry_for(base, hash_weights)
    deriv_entry = model_entry_for(derivative, hash_weights)
    if report is not None:
        for side, entry in (("base", base_entry), ("derivative", deriv_entry)):
            want = report["manifest"][side].get("weights_root")
            if want and entry.get("weights_root") and want != entry["weights_root"]:
                raise InterpError(f"{side} weights differ from the audited model")
    manifest = {
        "schema": "modeldiffr.causal.manifest/1",
        "base": base_entry,
        "derivative": deriv_entry,
        "layer": li,
        "suite": {"name": suite_name, "root": _items_root(loaded), "items": len(items)},
        "crosscoder": files.get("crosscoder.safetensors"),
        "features_id": features_doc["id"] if features_doc else None,
        "settings": {
            "top": list(top),
            "alphas": list(alphas),
            "resamples": n_resamples,
            "seed": seed,
        },
        "code": {"package": "modeldiffr", "version": __version__},
    }
    behavior = {
        "metric": "probability of the correct option",
        "base": round(sum(p_base) / len(p_base), 6),
        "derivative": round(sum(p_deriv) / len(p_deriv), 6),
    }
    doc = finalize(
        {
            "schema": SCHEMA,
            "created_at": now(),
            "modeldiffr_version": __version__,
            "manifest": manifest,
            "audit": {"audit_id": report["audit_id"], "changed": report["verdict"]["changed"]}
            if report
            else None,
            "behavior": behavior,
            "conditions": results,
            "top_features": ranked[:50],
            "files": {},
        }
    )
    out = Path(out)
    write(doc, out, "causal.json")
    from modeldiffr.interp.html import render_causal

    (out / "causal.html").write_text(render_causal(doc), encoding="utf-8")
    return doc
