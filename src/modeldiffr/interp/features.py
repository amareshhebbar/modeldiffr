import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from modeldiffr.interp.crosscoder import CLASSES, CrosscoderConfig, classify, feature_activations
from modeldiffr.interp.model import InterpError
from modeldiffr.proof.canonical import canonical_json, object_hash, sha256_hex

SCHEMA = "modeldiffr.features/1"
ID_PREFIX = "mdrf1:"
LABEL_PROMPT = (
    "Below are text snippets where one feature of a language model is most active. "
    "The token where it fires is wrapped in [[ ]]. Reply with a short noun phrase of at most "
    "eight words that describes what the feature responds to. Reply with the phrase only.\n\n"
    "{examples}"
)


def label_prompt_hash() -> str:
    return "sha256:" + sha256_hex(LABEL_PROMPT.encode("utf-8"))


def api_labeler(api_base: str, model: str, api_key: str | None = None, timeout: float = 60):
    url = api_base.rstrip("/") + "/chat/completions"

    def label(prompt: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 24,
            }
        ).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        if api_key:
            req.add_header("Authorization", f"Bearer {api_key}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip().splitlines()[0][:120]

    return label


def _context(tokenizer, ids, pos, before=12, after=3) -> dict:
    lo = max(0, pos - before)
    return {
        "before": tokenizer.decode(ids[lo:pos]),
        "token": tokenizer.decode(ids[pos : pos + 1]),
        "after": tokenizer.decode(ids[pos + 1 : pos + 1 + after]),
    }


def _select(labels, rel, density, per_class: int) -> list[int]:
    chosen = []
    for cls in ("derivative_only", "base_only", "shifted", "shared"):
        idx = [i for i, c in enumerate(labels) if c == cls]
        if cls == "derivative_only":
            idx.sort(key=lambda i: (-rel[i], -density[i]))
        elif cls == "base_only":
            idx.sort(key=lambda i: (rel[i], -density[i]))
        else:
            idx.sort(key=lambda i: -density[i])
        chosen += idx[:per_class]
    return chosen


def analyze(
    model,
    acts,
    layer: int,
    tokenizer,
    per_class: int = 20,
    n_examples: int = 8,
    labeler=None,
    progress=lambda _: None,
) -> dict:
    import torch

    xb, xd = acts.base[layer], acts.derivative[layer]
    f_size = model.b_enc.shape[0]
    counts = torch.zeros(f_size)
    maxes = torch.zeros(f_size)
    for _, f in feature_activations(model, xb, xd):
        counts += (f > 0).float().sum(0)
        maxes = torch.maximum(maxes, f.max(0).values)
    density = (counts / max(1, xb.shape[0])).tolist()
    labels, rel, cos = classify(model, density)
    chosen = _select(labels, rel, density, per_class)
    top_vals = {i: torch.full((n_examples,), -1.0) for i in chosen}
    top_idx = {i: torch.full((n_examples,), -1, dtype=torch.long) for i in chosen}
    sel = torch.tensor(chosen, dtype=torch.long) if chosen else None
    if sel is not None:
        for start, f in feature_activations(model, xb, xd):
            sub = f[:, sel]
            k = min(n_examples, sub.shape[0])
            vals, idx = sub.topk(k, dim=0)
            for col, i in enumerate(chosen):
                v = torch.cat([top_vals[i], vals[:, col]])
                j = torch.cat([top_idx[i], idx[:, col] + start])
                order = v.topk(n_examples).indices
                top_vals[i], top_idx[i] = v[order], j[order]
    features = []
    for n, i in enumerate(chosen):
        examples = []
        for v, j in zip(top_vals[i].tolist(), top_idx[i].tolist(), strict=True):
            if j < 0 or v <= 0:
                continue
            doc, pos = acts.tokens[j]
            examples.append({"activation": round(v, 4), **_context(tokenizer, acts.ids[doc], pos)})
        label = None
        if labeler and examples:
            text = "\n".join(f"{e['before']}[[{e['token']}]]{e['after']}" for e in examples)
            try:
                label = labeler(LABEL_PROMPT.format(examples=text))
            except Exception as exc:
                progress(f"labeling feature {i} failed: {exc}")
        features.append(
            {
                "index": i,
                "class": labels[i],
                "relative_norm": round(rel[i], 6),
                "decoder_cosine": round(cos[i], 6),
                "density": round(density[i], 8),
                "max_activation": round(float(maxes[i]), 4),
                "label": label,
                "label_verified": False,
                "examples": examples,
            }
        )
        if (n + 1) % 10 == 0:
            progress(f"collected examples for {n + 1} of {len(chosen)} features")
    hist = [0] * 20
    for i, c in enumerate(labels):
        if c != "dead":
            hist[min(19, int(rel[i] * 20))] += 1
    return {
        "classes": {c: labels.count(c) for c in CLASSES},
        "relative_norm_histogram": hist,
        "features": features,
    }


def feature_manifest(
    base_entry, deriv_entry, corpus: dict, layer: int, cfg: CrosscoderConfig, labeling, version: str
) -> dict:
    return {
        "schema": "modeldiffr.features.manifest/1",
        "base": base_entry,
        "derivative": deriv_entry,
        "corpus": corpus,
        "layer": layer,
        "crosscoder": cfg.to_dict(),
        "labeling": labeling,
        "code": {"package": "modeldiffr", "version": version},
    }


def finalize(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("result_sha256", None)
    doc["id"] = ID_PREFIX + sha256_hex(canonical_json(doc["manifest"]))
    doc["result_sha256"] = object_hash({k: v for k, v in doc.items() if k != "result_sha256"})
    return doc


def verify_features(path: str | Path) -> dict:
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    checks = []

    def c(name, ok, detail):
        checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})

    if doc.get("schema") != SCHEMA:
        return {
            "ok": False,
            "id": doc.get("id"),
            "checks": [{"name": "schema", "status": "fail", "detail": "not a features file"}],
        }
    want = ID_PREFIX + sha256_hex(canonical_json(doc["manifest"]))
    c(
        "features_id",
        want == doc.get("id"),
        want if want == doc.get("id") else f"manifest hashes to {want}",
    )
    body = {k: v for k, v in doc.items() if k != "result_sha256"}
    got = object_hash(body)
    c(
        "result_hash",
        got == doc.get("result_sha256"),
        "results match their hash" if got == doc.get("result_sha256") else "results were changed",
    )
    counts = {cls: 0 for cls in CLASSES}
    counts.update(doc["classes"])
    c(
        "classes",
        sum(counts.values()) == doc["manifest"]["crosscoder"]["dict_size"],
        f"{sum(counts.values())} features classified",
    )
    w = doc.get("weights") or {}
    wp = p.parent / w.get("file", "")
    if w.get("file") and wp.exists():
        h = "sha256:" + hashlib.sha256(wp.read_bytes()).hexdigest()
        c(
            "crosscoder_weights",
            h == w.get("sha256"),
            w["file"] if h == w.get("sha256") else "weights file differs from the recorded hash",
        )
    else:
        checks.append(
            {
                "name": "crosscoder_weights",
                "status": "skip",
                "detail": "weights file not next to features.json",
            }
        )
    return {"ok": all(x["status"] != "fail" for x in checks), "id": doc.get("id"), "checks": checks}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = [
    "InterpError",
    "SCHEMA",
    "analyze",
    "api_labeler",
    "feature_manifest",
    "finalize",
    "label_prompt_hash",
    "now",
    "verify_features",
]
