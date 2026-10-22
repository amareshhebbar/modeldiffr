import json
from pathlib import Path

from modeldiffr.interp.artifact import finalize
from modeldiffr.interp.capture import capture
from modeldiffr.interp.corpus import corpus_root
from modeldiffr.interp.crosscoder import CrosscoderConfig, save, train
from modeldiffr.interp.features import (
    SCHEMA,
    analyze,
    feature_manifest,
    label_prompt_hash,
    now,
)
from modeldiffr.interp.layerwise import compare_layers
from modeldiffr.interp.model import InterpError, resolve_layers, unwrap


def model_entry_for(backend, hash_weights: bool) -> dict:
    from modeldiffr.proof.manifest import model_entry

    fp = None
    if hasattr(backend, "fingerprint"):
        try:
            fp = backend.fingerprint(weights=hash_weights)
        except Exception:
            fp = None
    return model_entry(backend.metadata(), fp)


def run_layers(
    base, derivative, texts, layers="all", max_tokens=20000, max_length=256, progress=lambda _: None
):
    model, _ = unwrap(base)
    chosen = resolve_layers(model, layers)
    acts = capture(
        base,
        derivative,
        texts,
        chosen,
        max_tokens=max_tokens,
        max_length=max_length,
        progress=progress,
    )
    return {
        "tokens": acts.n,
        "texts": acts.texts_used,
        "skipped": acts.texts_skipped,
        "layers": compare_layers(acts),
    }


def run_feature_diff(
    base,
    derivative,
    texts: list[str],
    corpus_source: str,
    out: str | Path,
    layer="middle",
    cfg: CrosscoderConfig | None = None,
    max_tokens: int = 50000,
    max_length: int = 256,
    per_class: int = 20,
    n_examples: int = 8,
    labeler=None,
    labeler_model: str | None = None,
    report: dict | None = None,
    hash_weights: bool = True,
    progress=lambda _: None,
) -> dict:
    from modeldiffr import __version__

    cfg = cfg or CrosscoderConfig()
    model, tok = unwrap(base)
    chosen = resolve_layers(model, layer)
    if len(chosen) != 1:
        raise InterpError("a crosscoder is trained on one layer; pass --layer N")
    li = chosen[0]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    progress(f"capturing layer {li} activations")
    acts = capture(
        base,
        derivative,
        texts,
        [li],
        max_tokens=max_tokens,
        max_length=max_length,
        progress=progress,
    )
    if acts.n < 64:
        raise InterpError(f"only {acts.n} tokens captured; give a larger corpus")
    progress(
        f"training a {cfg.variant} crosscoder with {cfg.dict_size} features on {acts.n} tokens"
    )
    xc, stats = train(acts.base[li], acts.derivative[li], cfg, progress=progress)
    weights_file = out / "crosscoder.safetensors"
    weights_hash = save(xc, weights_file, cfg)
    layer_stats = compare_layers(acts)[0]
    progress("classifying features and collecting examples")
    result = analyze(
        xc,
        acts,
        li,
        tok,
        per_class=per_class,
        n_examples=n_examples,
        labeler=labeler,
        progress=progress,
    )
    base_entry = model_entry_for(base, hash_weights)
    deriv_entry = model_entry_for(derivative, hash_weights)
    corpus = {
        "source": corpus_source,
        "texts": len(texts),
        "texts_used": acts.texts_used,
        "texts_skipped": acts.texts_skipped,
        "tokens": acts.n,
        "max_length": max_length,
        "root": corpus_root(texts),
    }
    labeling = {"model": labeler_model, "prompt_sha256": label_prompt_hash()} if labeler else None
    manifest = feature_manifest(base_entry, deriv_entry, corpus, li, cfg, labeling, __version__)
    links = None
    if report is not None:
        problems = []
        for side, entry in (("base", base_entry), ("derivative", deriv_entry)):
            want = report["manifest"][side].get("weights_root")
            if want and entry.get("weights_root") and want != entry["weights_root"]:
                problems.append(f"{side} weights differ from the audited model")
        if problems:
            raise InterpError("; ".join(problems))
        links = {"audit_id": report["audit_id"], "changed": report["verdict"]["changed"]}
    doc = finalize(
        {
            "schema": SCHEMA,
            "created_at": now(),
            "modeldiffr_version": __version__,
            "manifest": manifest,
            "audit": links,
            "layer_stats": layer_stats,
            "training": stats,
            "files": {weights_file.name: weights_hash},
            **result,
        }
    )
    (out / "features.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    from modeldiffr.interp.html import render_features

    (out / "features.html").write_text(render_features(doc), encoding="utf-8")
    return doc
