import sys


def _log(message: str) -> None:
    print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)


def _scan_args(p) -> None:
    p.add_argument("--probes", type=int, default=300)
    p.add_argument("--gen-tokens", type=int, default=16)
    p.add_argument("--z", type=float, default=6.0, help="Robust z score that counts as an outlier.")
    p.add_argument("--min-kl", type=float, default=0.05, help="Smallest divergence that can flag.")
    p.add_argument(
        "--ratio",
        type=float,
        default=4.0,
        help="Search result over median random trigger that flags.",
    )
    p.add_argument("--search-steps", type=int, default=40, help="0 skips the trigger search.")
    p.add_argument("--trigger-len", type=int, default=4)
    p.add_argument("--restarts", type=int, default=2)
    p.add_argument("--null-samples", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)


def _scan_kwargs(args) -> dict:
    return {
        "probes": args.probes,
        "gen_tokens": args.gen_tokens,
        "z_threshold": args.z,
        "min_kl": args.min_kl,
        "ratio_threshold": args.ratio,
        "search_steps": args.search_steps,
        "trigger_len": args.trigger_len,
        "restarts": args.restarts,
        "null_samples": args.null_samples,
        "seed": args.seed,
    }


def register(sub) -> dict:
    scan = sub.add_parser("scan", help="Look for inputs where the derivative behaves unusually.")
    scan.add_argument("base")
    scan.add_argument("derivative")
    scan.add_argument("--device", default="auto")
    scan.add_argument("--dtype", default="auto", choices=["auto", "float32", "float16", "bfloat16"])
    scan.add_argument("--trust-remote-code", action="store_true")
    scan.add_argument("--no-weight-hash", action="store_true")
    scan.add_argument("--out", default="modeldiffr_scan")
    _scan_args(scan)

    zoo = sub.add_parser("zoo", help="Build and score a zoo of backdoored and clean models.")
    zsub = zoo.add_subparsers(dest="zoo_command", required=True)
    make = zsub.add_parser(
        "make", help="Fine tune copies of a model, some with a harmless trigger."
    )
    make.add_argument("base")
    make.add_argument("--out", required=True)
    make.add_argument("--backdoored", type=int, default=2)
    make.add_argument("--clean", type=int, default=2)
    make.add_argument("--steps", type=int, default=300)
    make.add_argument("--lr", type=float, default=1e-4)
    make.add_argument("--batch", type=int, default=8)
    make.add_argument("--trigger-words", type=int, default=2)
    make.add_argument("--poison-rate", type=float, default=0.3)
    make.add_argument("--device", default="cpu")
    make.add_argument("--seed", type=int, default=0)
    ev = zsub.add_parser("eval", help="Scan every zoo model and report detection rates.")
    ev.add_argument("zoo")
    ev.add_argument("--device", default="cpu")
    _scan_args(ev)
    return {"scan": _scan, "zoo": _zoo}


def _rate(x, ci) -> str:
    if x is None:
        return "n/a"
    return f"{x:.0%} (95% interval {ci[0]:.0%} to {ci[1]:.0%})"


def _scan(args) -> int:
    from modeldiffr.backend import HFBackend
    from modeldiffr.scan.run import run_scan

    _log(f"loading {args.base} and {args.derivative}")
    base = HFBackend(args.base, args.device, None, args.dtype, args.trust_remote_code)
    deriv = HFBackend(args.derivative, args.device, None, args.dtype, args.trust_remote_code)
    doc = run_scan(
        base,
        deriv,
        args.out,
        hash_weights=not args.no_weight_hash,
        progress=_log,
        **_scan_kwargs(args),
    )
    s = doc["summary"]
    print(f"\nscan id {doc['id']}")
    print(f"{s['probes']} probes, {s['outliers']} outliers, median divergence {s['kl_median']:.4f}")
    if doc.get("search"):
        se = doc["search"]
        print(
            f"trigger search: {se['trigger']!r} divergence {se['kl']:.4f}, "
            f"{se['ratio']:.1f} times the median random trigger"
        )
    print("flagged for review" if doc["flagged"] else "nothing above the threshold")
    print(f"report: {args.out}/scan.html")
    return 0


def _zoo(args) -> int:
    from modeldiffr.scan.zoo import eval_zoo, make_zoo

    if args.zoo_command == "make":
        zoo = make_zoo(
            args.base,
            args.out,
            backdoored=args.backdoored,
            clean=args.clean,
            steps=args.steps,
            lr=args.lr,
            batch=args.batch,
            trigger_words=args.trigger_words,
            poison_rate=args.poison_rate,
            device=args.device,
            seed=args.seed,
            progress=_log,
        )
        print(f"wrote {len(zoo['models'])} models to {args.out}")
        print("answers.json holds the triggers; keep it away from whoever runs the scan")
        return 0
    res = eval_zoo(args.zoo, device=args.device, progress=_log, **_scan_kwargs(args))
    for r in res["models"]:
        print(
            f"{r['name']}  {r['kind']:<10}  {'flagged' if r['flagged'] else 'clear':<8}  "
            f"{r['found_trigger']!r}"
        )
    print(
        f"\ndetection {res['detected']} of {res['backdoored']}: "
        f"{_rate(res['detection_rate'], res['detection_ci'])}"
    )
    print(
        f"false positives {res['false_positives']} of {res['clean']}: "
        f"{_rate(res['false_positive_rate'], res['false_positive_ci'])}"
    )
    return 0
