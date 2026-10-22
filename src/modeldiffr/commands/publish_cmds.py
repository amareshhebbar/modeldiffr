import sys


def _log(message: str) -> None:
    print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)


def register(sub) -> dict:
    controls = sub.add_parser("controls", help="Make models with planted changes to test audits.")
    csub = controls.add_subparsers(dest="controls_command", required=True)
    make = csub.add_parser("make", help="Write a copy of a model with a known perturbation.")
    make.add_argument("base", help="Base model id or local path with safetensors weights.")
    make.add_argument("--out", required=True)
    make.add_argument(
        "--kind", default="noise", choices=["identity", "noise", "scale", "zero", "prune"]
    )
    make.add_argument(
        "--strength",
        type=float,
        default=0.05,
        help="noise: std as a share of each tensor's std; scale: factor; prune: share zeroed.",
    )
    make.add_argument("--match", default=None, help="Regular expression for tensor names.")
    make.add_argument("--seed", type=int, default=0)
    make.add_argument("--revision", default=None)

    batch = sub.add_parser("batch", help="Run many audits from a YAML or JSON file.")
    batch.add_argument("spec")
    batch.add_argument("--out", default=None, help="Folder for all audits (default: spec out).")
    batch.add_argument("--only", default=None, help="Comma separated audit names to run.")
    batch.add_argument(
        "--rerun", action="store_true", help="Run audits that already have a report."
    )
    batch.add_argument("--dry-run", action="store_true", help="Print the commands and stop.")

    reg = sub.add_parser("registry", help="Build a static site that lists and verifies audits.")
    rsub = reg.add_subparsers(dest="registry_command", required=True)
    build = rsub.add_parser("build", help="Collect reports into a static registry site.")
    build.add_argument("paths", nargs="+", help="Report files or folders to search.")
    build.add_argument("--out", default="registry_site")
    build.add_argument("--title", default="Modeldiffr audit registry")
    build.add_argument(
        "--key", action="append", default=[], help="Publisher key as NAME=PUBLIC_KEY_PATH."
    )
    build.add_argument("--allow-failed", action="store_true", help="List reports that fail.")
    build.add_argument("--base-url", default="")
    return {"controls": _controls, "batch": _batch, "registry": _registry}


def _controls(args) -> int:
    from modeldiffr.controls import make_control

    rec = make_control(
        args.base,
        args.out,
        kind=args.kind,
        strength=args.strength,
        match=args.match,
        seed=args.seed,
        revision=args.revision,
        progress=_log,
    )
    print(f"wrote {args.out}: {args.kind} {args.strength} on {len(rec['tensors_changed'])} tensors")
    print(f"an audit against {args.base} should find: {rec['expect'].replace('_', ' ')}")
    return 0


def _rate(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def _batch(args) -> int:
    from modeldiffr.batch import run_batch

    only = [x.strip() for x in args.only.split(",")] if args.only else None
    index = run_batch(
        args.spec,
        out=args.out,
        only=only,
        resume=not args.rerun,
        dry_run=args.dry_run,
        progress=_log,
    )
    if args.dry_run:
        for row in index["audits"]:
            print(row["command"])
        return 0
    for row in index["audits"]:
        verdict = row.get("verdict")
        if verdict is None:
            text = f"failed ({row.get('error') or 'exit ' + str(row.get('exit_code'))})"
        else:
            text = ", ".join(verdict["changed"]) or "no significant change"
        tail = f"  [{row['outcome']}]" if row.get("outcome") else ""
        print(f"{row['name']:<28} {row['status']:<9} {text}{tail}")
    s = index["summary"]
    print(
        f"\n{s['completed']} of {s['audits']} audits complete, {s['failed']} failed; "
        f"planted changes found {s['detected']} of {s['planted']} ({_rate(s['detection_rate'])}), "
        f"false positives {s['false_positives']} of {s['controls_clean']} "
        f"({_rate(s['false_positive_rate'])})"
    )
    return 0 if s["failed"] == 0 else 5


def _registry(args) -> int:
    from modeldiffr.registry import build_registry

    keys = {}
    for item in args.key:
        name, _, path = item.partition("=")
        if not path:
            print(f"error: --key needs NAME=PATH, got {item}", file=sys.stderr)
            return 2
        keys[name] = path
    reg = build_registry(
        args.paths,
        args.out,
        title=args.title,
        keys=keys,
        allow_failed=args.allow_failed,
        base_url=args.base_url,
        progress=_log,
    )
    print(f"wrote {args.out} with {len(reg['audits'])} audits")
    for s in reg["skipped"]:
        print(f"skipped {s['path']}: {', '.join(s['failed'])} failed")
    print(f"preview: python -m http.server --directory {args.out} 8000")
    return 0 if not reg["skipped"] else 4
