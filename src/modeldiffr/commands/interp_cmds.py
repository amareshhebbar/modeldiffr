import json
import sys


def _log(message: str) -> None:
    print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)


def _model_args(p) -> None:
    p.add_argument("base")
    p.add_argument("derivative")
    p.add_argument("--device", default="auto")
    p.add_argument("--dtype", default="auto", choices=["auto", "float32", "float16", "bfloat16"])
    p.add_argument("--base-revision", default=None)
    p.add_argument("--derivative-revision", default=None)
    p.add_argument("--trust-remote-code", action="store_true")


def _corpus_args(p, limit: int, tokens: int) -> None:
    p.add_argument(
        "--corpus",
        default="builtin",
        help="builtin, a .jsonl or .txt file, or hf:DATASET[:CONFIG]:SPLIT",
    )
    p.add_argument("--field", default="text", help="Field holding the text in jsonl or datasets.")
    p.add_argument("--texts", type=int, default=limit, help="At most this many texts.")
    p.add_argument("--max-tokens", type=int, default=tokens)
    p.add_argument("--max-length", type=int, default=256, help="Tokens per text.")


def register(sub) -> dict:
    layers = sub.add_parser("layers", help="Compare hidden states of both models layer by layer.")
    _model_args(layers)
    _corpus_args(layers, 500, 20000)
    layers.add_argument("--layers", default="all", help="all, middle, 3, -1 or 2-5,8")
    layers.add_argument("--json", action="store_true")

    dirs = sub.add_parser(
        "directions", help="Compare a difference of means direction in both models."
    )
    _model_args(dirs)
    dirs.add_argument("--positive", required=True, help="Texts with the property, .jsonl or .txt")
    dirs.add_argument("--negative", required=True, help="Texts without it, .jsonl or .txt")
    dirs.add_argument("--field", default="text")
    dirs.add_argument("--layers", default="all")
    dirs.add_argument("--json", action="store_true")

    feats = sub.add_parser(
        "features", help="Train a crosscoder and find new, lost and shifted features."
    )
    _model_args(feats)
    _corpus_args(feats, 5000, 50000)
    feats.add_argument("--layer", default="middle")
    feats.add_argument("--dict-size", type=int, default=4096)
    feats.add_argument("--k", type=int, default=32, help="Active features per token on average.")
    feats.add_argument("--variant", default="standard", choices=["standard", "delta"])
    feats.add_argument("--steps", type=int, default=2000)
    feats.add_argument("--batch-size", type=int, default=2048)
    feats.add_argument("--lr", type=float, default=5e-4)
    feats.add_argument("--seed", type=int, default=0)
    feats.add_argument(
        "--per-class", type=int, default=20, help="Features with examples per class."
    )
    feats.add_argument("--examples", type=int, default=8)
    feats.add_argument("--report", default=None, help="Link to a behavioral report.json.")
    feats.add_argument("--label-api", default=None, help="OpenAI compatible endpoint for labels.")
    feats.add_argument("--label-model", default=None)
    feats.add_argument("--no-weight-hash", action="store_true")
    feats.add_argument("--out", default="modeldiffr_features")

    causal = sub.add_parser(
        "causal", help="Patch and steer one layer to measure how much of a change it carries."
    )
    _model_args(causal)
    causal.add_argument("--layer", default="middle")
    causal.add_argument("--suite", default="quick")
    causal.add_argument("--tasks", default=None, help="Comma separated multiple choice tasks.")
    causal.add_argument("--limit", type=int, default=200, help="Items per task.")
    causal.add_argument("--data-dir", default=None)
    causal.add_argument("--features", default=None, help="Folder with features.json and weights.")
    causal.add_argument("--top", default="10,50,200", help="Feature set sizes to patch.")
    causal.add_argument("--alphas", default="0.5,1,2", help="Steering strengths.")
    causal.add_argument("--resamples", type=int, default=2000)
    causal.add_argument("--seed", type=int, default=0)
    causal.add_argument("--report", default=None, help="Link to a behavioral report.json.")
    causal.add_argument("--no-weight-hash", action="store_true")
    causal.add_argument("--out", default="modeldiffr_causal")
    return {
        "layers": _layers,
        "directions": _directions,
        "features": _features,
        "causal": _causal,
    }


def _load(args):
    from modeldiffr.backend import HFBackend
    from modeldiffr.integrations.hub import parse_model_ref

    out = []
    for side in ("base", "derivative"):
        model, ref = parse_model_ref(getattr(args, side))
        _log(f"loading {side} model {model}")
        out.append(
            HFBackend(
                model,
                args.device,
                getattr(args, f"{side}_revision") or ref,
                args.dtype,
                args.trust_remote_code,
            )
        )
    return out


def _layers(args) -> int:
    from modeldiffr.interp.corpus import load_corpus
    from modeldiffr.interp.run import run_layers

    texts = load_corpus(args.corpus, args.texts, args.field)
    base, deriv = _load(args)
    res = run_layers(base, deriv, texts, args.layers, args.max_tokens, args.max_length, _log)
    if args.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"{res['tokens']} tokens from {res['texts']} texts ({res['skipped']} skipped)")
    print(
        f"{'layer':>5}  {'CKA':>7}  {'cosine':>7}  {'rel change':>10}  "
        f"{'mean shift':>10}  {'norm ratio':>10}"
    )
    for r in res["layers"]:
        print(
            f"{r['layer']:>5}  {r['cka']:>7.4f}  {r['cosine']:>7.4f}  "
            f"{r['relative_change']:>10.4f}  "
            f"{r['mean_shift']:>10.4f}  {r['norm_ratio']:>10.4f}"
        )
    most = max(res["layers"], key=lambda r: r["relative_change"])
    print(f"\nlargest change at layer {most['layer']}")
    return 0


def _directions(args) -> int:
    from modeldiffr.interp.corpus import load_corpus
    from modeldiffr.interp.directions import compare_directions
    from modeldiffr.interp.model import resolve_layers

    pos = load_corpus(args.positive, 100000, args.field)
    neg = load_corpus(args.negative, 100000, args.field)
    base, deriv = _load(args)
    rows = compare_directions(base, deriv, pos, neg, resolve_layers(base.model, args.layers))
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(f"{len(pos)} positive and {len(neg)} negative texts")
    print(f"{'layer':>5}  {'cosine':>7}  {'base sep':>9}  {'deriv sep':>9}  {'ratio':>7}")
    for r in rows:
        ratio = "n/a" if r["separation_ratio"] is None else f"{r['separation_ratio']:.3f}"
        print(
            f"{r['layer']:>5}  {r['cosine']:>7.4f}  {r['separation_base']:>9.4f}  "
            f"{r['separation_derivative']:>9.4f}  {ratio:>7}"
        )
    return 0


def _features(args) -> int:
    import os

    from modeldiffr.interp.corpus import load_corpus
    from modeldiffr.interp.crosscoder import CrosscoderConfig
    from modeldiffr.interp.features import api_labeler
    from modeldiffr.interp.run import run_feature_diff

    report = None
    if args.report:
        with open(args.report, encoding="utf-8") as f:
            report = json.load(f)
    labeler = None
    if args.label_api:
        if not args.label_model:
            print("error: --label-api needs --label-model", file=sys.stderr)
            return 2
        key = os.environ.get("MODELDIFFR_API_KEY") or os.environ.get("OPENAI_API_KEY")
        labeler = api_labeler(args.label_api, args.label_model, key)
    texts = load_corpus(args.corpus, args.texts, args.field)
    cfg = CrosscoderConfig(
        dict_size=args.dict_size,
        k=args.k,
        variant=args.variant,
        steps=args.steps,
        batch_size=args.batch_size,
        lr=args.lr,
        seed=args.seed,
    )
    base, deriv = _load(args)
    doc = run_feature_diff(
        base,
        deriv,
        texts,
        args.corpus,
        args.out,
        layer=args.layer,
        cfg=cfg,
        max_tokens=args.max_tokens,
        max_length=args.max_length,
        per_class=args.per_class,
        n_examples=args.examples,
        labeler=labeler,
        labeler_model=args.label_model,
        report=report,
        hash_weights=not args.no_weight_hash,
        progress=_log,
    )
    c = doc["classes"]
    t = doc["training"]
    print(f"\nfeatures id {doc['id']}")
    print(
        f"layer {doc['manifest']['layer']}: {c['derivative_only']} new, {c['base_only']} lost, "
        f"{c['shifted']} shifted, {c['shared']} shared, {c['dead']} never active"
    )
    print(
        f"variance explained base {t.get('fve_base', 0):.3f}, "
        f"derivative {t.get('fve_derivative', 0):.3f}"
    )
    print(f"report: {args.out}/features.html")
    return 0


def _causal(args) -> int:
    from modeldiffr.audit import load_items
    from modeldiffr.interp.causal_run import run_causal
    from modeldiffr.tasks.registry import task_suite

    only = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
    suite = task_suite(args.suite, only, args.limit)
    loaded = load_items(suite, args.data_dir, None, _log)
    report = None
    if args.report:
        with open(args.report, encoding="utf-8") as f:
            report = json.load(f)
    base, deriv = _load(args)
    doc = run_causal(
        base,
        deriv,
        loaded,
        args.suite,
        args.out,
        layer=args.layer,
        features_dir=args.features,
        top=tuple(int(x) for x in args.top.split(",") if x.strip()),
        alphas=tuple(float(x) for x in args.alphas.split(",") if x.strip()),
        n_resamples=args.resamples,
        seed=args.seed,
        report=report,
        hash_weights=not args.no_weight_hash,
        progress=_log,
    )
    b = doc["behavior"]
    first = doc["conditions"][0]
    print(f"\ncausal id {doc['id']}")
    print(
        f"probability of the correct option: base {b['base']:.4f}, "
        f"derivative {b['derivative']:.4f}, "
        f"change {first['behavior_delta']:+.4f}"
    )
    for r in doc["conditions"]:
        if r["share"] is None or not r["explainable"]:
            text = "no significant change to explain"
        else:
            lo, hi = r["share_ci"] or (r["share"], r["share"])
            text = f"{r['share'] * 100:6.1f}%  [{lo * 100:.1f}, {hi * 100:.1f}]"
        print(f"{r['name']:<24} {text}")
    print(f"report: {args.out}/causal.html")
    return 0
