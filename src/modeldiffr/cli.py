import argparse
import json
import sys

from modeldiffr import __version__
from modeldiffr.backend import MissingDependencyError
from modeldiffr.checks import TEMPLATE_MODES, ComparabilityError
from modeldiffr.errors import ModeldiffrError
from modeldiffr.suites import SUITES


def _command_modules():
    import importlib
    import pkgutil

    import modeldiffr.commands as pkg

    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        yield importlib.import_module(f"modeldiffr.commands.{info.name}")


def _build_parser(handlers: dict | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modeldiffr",
        description="Audit what changed between a base LLM and a derivative model.",
    )
    parser.add_argument("--version", action="version", version=f"modeldiffr {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Compare a base model with a derivative model.")
    audit.add_argument("base", help="Base model id or local path.")
    audit.add_argument("derivative", help="Derivative model id or local path.")
    audit.add_argument(
        "--suite",
        default="quick",
        help="quick (built in, no downloads), lite, standard or full. See modeldiffr suites.",
    )
    audit.add_argument("--tasks", default=None, help="Comma separated tasks to run from the suite.")
    audit.add_argument("--limit", type=int, default=None, help="At most this many items per task.")
    audit.add_argument(
        "--data-dir", default=None, help="Folder with TASK.jsonl files for offline use."
    )
    audit.add_argument(
        "--allow-code-execution",
        action="store_true",
        help="Run model written code for humaneval in a sandboxed subprocess.",
    )
    audit.add_argument(
        "--refusal-detector",
        default="keyword",
        help="keyword, or hf:MODEL_ID[@LABEL] for a text classification model.",
    )
    audit.add_argument(
        "--fdr", type=float, default=0.05, help="False discovery rate across metrics."
    )
    audit.add_argument(
        "--estimate", action="store_true", help="Time a few calls and print the expected run time."
    )
    audit.add_argument(
        "--plan-only",
        action="store_true",
        help="Load the suite, print the plan, estimate the run time and stop.",
    )
    audit.add_argument(
        "--backend", default="auto", help="hf, vllm, llamacpp or api for both models."
    )
    audit.add_argument("--base-backend", default=None, help="Backend for the base model.")
    audit.add_argument(
        "--derivative-backend", default=None, help="Backend for the derivative model."
    )
    audit.add_argument(
        "--api-base", default=None, help="OpenAI compatible endpoint for the api backend."
    )
    audit.add_argument("--n-ctx", type=int, default=4096, help="Context size for llama.cpp.")
    audit.add_argument("--n-gpu-layers", type=int, default=0, help="Layers on GPU for llama.cpp.")
    audit.add_argument("--out", default="modeldiffr_report", help="Output directory.")
    audit.add_argument("--device", default="auto", help="auto, cpu, cuda, cuda:0, or mps.")
    audit.add_argument(
        "--dtype", default="auto", choices=["auto", "float32", "float16", "bfloat16"]
    )
    audit.add_argument("--base-revision", default=None, help="Pin the base model revision.")
    audit.add_argument("--derivative-revision", default=None, help="Pin the derivative revision.")
    audit.add_argument("--seed", type=int, default=0)
    audit.add_argument("--resamples", type=int, default=2000)
    audit.add_argument("--trust-remote-code", action="store_true")
    audit.add_argument(
        "--fail-on-change",
        action="store_true",
        help="Exit with code 1 when any metric changes significantly (CI gate mode).",
    )
    audit.add_argument(
        "--template",
        default="auto",
        choices=TEMPLATE_MODES,
        help="Which chat template renders generation prompts. auto uses one shared template "
        "when the templates differ and the tokenizers match.",
    )
    audit.add_argument(
        "--no-weight-hash",
        action="store_true",
        help="Skip hashing weight files. Faster, but the report is not tied to exact weights.",
    )
    audit.add_argument(
        "--sign-key", default=None, help="Sign the report with this Ed25519 private key."
    )
    audit.add_argument(
        "--sigstore", action="store_true", help="Sign the report keylessly with Sigstore."
    )

    sub.add_parser("suites", help="List available suites.")
    sub.add_parser("tasks", help="List available tasks with their datasets.")

    power = sub.add_parser("power", help="Smallest change a task size can detect.")
    power.add_argument("--n", type=int, required=True, help="Number of paired items.")
    power.add_argument("--rate", type=float, default=0.5, help="Expected base accuracy or rate.")
    power.add_argument("--power", type=float, default=0.8)
    power.add_argument("--alpha", type=float, default=0.05)

    reval = sub.add_parser("refusal-eval", help="Measure a refusal detector on labeled responses.")
    reval.add_argument("file", help="JSONL with response and refused (true or false) per line.")
    reval.add_argument("--detector", default="keyword")

    verify = sub.add_parser("verify", help="Check that a report is internally consistent.")
    verify.add_argument("report", help="Path to report.json.")
    verify.add_argument(
        "--models",
        action="store_true",
        help="Also download or read both models and check their weights against the report.",
    )
    verify.add_argument("--json", action="store_true", help="Print the result as JSON.")
    verify.add_argument(
        "--suite-data",
        default=None,
        help="Rebuild dataset suites to check their root: hub, or a folder of TASK.jsonl files.",
    )
    verify.add_argument("--key", default=None, help="Public key for report.dsse.json.")
    verify.add_argument("--identity", default=None, help="Expected Sigstore signer identity.")
    verify.add_argument("--issuer", default=None, help="Expected Sigstore OIDC issuer.")
    verify.add_argument("--staging", action="store_true", help="Sigstore staging trust root.")
    verify.add_argument("--rpc", default=None, help="JSON RPC endpoint to check EAS anchors.")

    fp = sub.add_parser("fingerprint", help="Print content hashes for a model.")
    fp.add_argument("model", help="Model id or local path.")
    fp.add_argument("--revision", default=None)
    fp.add_argument("--leaves", action="store_true", help="Include the hash of every tensor.")
    fp.add_argument("--json", action="store_true", help="Print the result as JSON.")
    for module in _command_modules():
        found = module.register(sub)
        if handlers is not None:
            handlers.update(found)
    return parser


def _cmd_suites() -> int:
    from modeldiffr.tasks.registry import SIZES

    for name, suite in sorted(SUITES.items()):
        print(
            f"{name}: built in, {len(suite.capability)} capability items, "
            f"{len(suite.benign_prompts)} over refusal prompts, "
            f"{len(suite.neutral_texts)} divergence texts"
        )
    for name, sizes in SIZES.items():
        parts = [f"{t} {'all' if n is None else n}" for t, n in sizes.items()]
        print(f"{name}: {', '.join(parts)}")
    return 0


def _cmd_tasks() -> int:
    from modeldiffr.tasks.registry import build_tasks

    for name, task in build_tasks().items():
        src = task.source
        where = (
            f"{src.path} {src.config or ''} {src.split}@{(src.revision or 'main')[:10]}"
            if src
            else "built in"
        )
        metrics = ", ".join(m.name for m in task.metrics)
        print(f"{name:<15} {task.kind:<16} {where.strip():<60} {metrics}")
    return 0


def _cmd_power(args) -> int:
    from modeldiffr.stats import min_detectable_effect

    mde = min_detectable_effect(args.n, args.rate, args.alpha, args.power)
    print(
        f"with {args.n} paired items at a rate near {args.rate:.2f}, changes of about "
        f"{mde * 100:.1f} points are detected {args.power:.0%} of the time"
    )
    return 0


def _cmd_refusal_eval(args) -> int:
    from modeldiffr.tasks.refusal import make_detector

    with open(args.file, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    detector = make_detector(args.detector)
    got = detector.batch([r["response"] for r in rows])
    want = [bool(r["refused"]) for r in rows]
    tp = sum(g and w for g, w in zip(got, want, strict=True))
    tn = sum(not g and not w for g, w in zip(got, want, strict=True))
    fp = sum(g and not w for g, w in zip(got, want, strict=True))
    fn = sum(not g and w for g, w in zip(got, want, strict=True))
    n = len(rows)
    print(f"detector  {detector.name}")
    print(f"items     {n}")
    print(f"accuracy  {(tp + tn) / n:.4f}")
    print(f"precision {tp / (tp + fp) if tp + fp else 0:.4f}")
    print(f"recall    {tp / (tp + fn) if tp + fn else 0:.4f}")
    return 0


def _side_backend(args, side: str, model: str, revision):
    from modeldiffr.backends import detect_backend, make_backend
    from modeldiffr.integrations.hub import parse_model_ref

    model, ref = parse_model_ref(model)
    revision = revision or ref
    explicit = getattr(args, f"{side}_backend") or args.backend
    kind = detect_backend(model, explicit)
    return make_backend(
        kind,
        model,
        device=args.device,
        revision=revision,
        dtype=args.dtype,
        trust_remote_code=args.trust_remote_code,
        seed=args.seed,
        api_base=args.api_base,
        n_ctx=args.n_ctx,
        n_gpu_layers=args.n_gpu_layers,
    )


def _cmd_audit(args: argparse.Namespace) -> int:
    from modeldiffr.audit import AuditPlanError, load_items, plan, run_audit
    from modeldiffr.report import write_reports
    from modeldiffr.tasks.code import CodeExecutionNotAllowedError
    from modeldiffr.tasks.data import DatasetUnavailableError
    from modeldiffr.tasks.refusal import make_detector
    from modeldiffr.tasks.registry import task_suite

    def log(message: str) -> None:
        print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)

    only = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
    try:
        suite = task_suite(args.suite, only, args.limit, args.allow_code_execution)
    except KeyError as exc:
        print(f"error: {exc.args[0]}", file=sys.stderr)
        return 2
    if args.plan_only and not args.estimate:
        try:
            loaded = load_items(suite, args.data_dir, None, log)
        except DatasetUnavailableError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        for row in plan(loaded):
            mde = row["min_detectable_effect"]
            print(
                f"{row['task']:<15} {row['items']:>6} items  "
                f"{'' if mde is None else f'detects about {mde * 100:.1f} points'}"
            )
        return 0
    detector = make_detector(args.refusal_detector)
    log(f"loading base model {args.base}")
    base = _side_backend(args, "base", args.base, args.base_revision)
    log(f"loading derivative model {args.derivative}")
    derivative = _side_backend(args, "derivative", args.derivative, args.derivative_revision)
    if args.plan_only:
        from modeldiffr.audit import estimate_seconds

        loaded = load_items(suite, args.data_dir, None, log)
        rows = plan(loaded)
        seconds = estimate_seconds(base, derivative, rows)
        for row in rows:
            print(f"{row['task']:<15} {row['items']:>6} items")
        print(f"estimated run time {seconds / 60:.1f} minutes on this hardware")
        return 0
    try:
        result = run_audit(
            base,
            derivative,
            suite,
            seed=args.seed,
            n_resamples=args.resamples,
            progress=log,
            template=args.template,
            hash_weights=not args.no_weight_hash,
            refusal_detector=detector,
            allow_code_execution=args.allow_code_execution,
            data_dir=args.data_dir,
            fdr_q=args.fdr,
            estimate=args.estimate,
        )
    except ComparabilityError as exc:
        for issue in exc.issues:
            print(f"{issue['level']}: {issue['message']}", file=sys.stderr)
        return 3
    except (DatasetUnavailableError, CodeExecutionNotAllowedError, AuditPlanError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json_path, html_path = write_reports(result, args.out)

    print(f"\naudit id {result['audit_id']}")
    for issue in result["comparability"]["issues"]:
        if issue["level"] != "info":
            print(f"{issue['level']}: {issue['message']}")
    wd = result.get("weights_diff")
    if wd is not None:
        print(
            f"weights: {wd['changed_count']} of {wd['shared']} shared tensors changed, "
            f"{wd['added_count']} added, {wd['removed_count']} removed"
        )
    print()
    width = max([24] + [len(m["name"]) + 1 for m in result["metrics"]])
    for m in result["metrics"]:
        if m["significant"] and m.get("negligible"):
            flag = "changed, negligible"
        elif m["significant"]:
            flag = "CHANGED"
        else:
            flag = "within noise"
        print(
            f"{m['name']:<{width}} base {m['base_mean']:.4f}  "
            f"derivative {m['derivative_mean']:.4f}  "
            f"delta {m['delta']:+.4f}  95% CI [{m['ci_low']:+.4f}, {m['ci_high']:+.4f}]  "
            f"p {m['p_value']:.4f}  {flag}"
        )
    for note in result["notes"]:
        print(f"note: {note}")
    print(f"\nreport: {html_path}\njson:   {json_path}")

    if args.sign_key or args.sigstore:
        from modeldiffr.commands.proof_cmds import sign_report

        for path in sign_report(json_path, args.sign_key, args.sigstore):
            print(f"signed: {path}")
    if args.fail_on_change and result["verdict"]["any_change"]:
        return 1
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from modeldiffr.proof.verify import verify_file

    def log(message: str) -> None:
        print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)

    try:
        with open(args.report, encoding="utf-8") as f:
            schema = json.load(f).get("schema")
        if schema == "modeldiffr.features/1":
            from modeldiffr.interp.features import verify_features

            result = verify_features(args.report)
        elif isinstance(schema, str) and schema.startswith("modeldiffr."):
            from modeldiffr.interp.artifact import verify_artifact

            result = verify_artifact(args.report)
        else:
            result = verify_file(
                args.report,
                check_models=args.models,
                progress=log,
                suite_data=args.suite_data,
                key=args.key,
                identity=args.identity,
                issuer=args.issuer,
                staging=args.staging,
                rpc=args.rpc,
            )
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: cannot read report: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"audit id {result.get('audit_id') or result.get('id')}")
        for c in result["checks"]:
            print(f"{c['status'].upper():<5} {c['name']:<26} {c['detail']}")
        print("\nverified" if result["ok"] else "\nverification FAILED")
    return 0 if result["ok"] else 4


def _cmd_fingerprint(args: argparse.Namespace) -> int:
    from modeldiffr.fingerprint import resolve_model_dir, tokenizer_fingerprint, weights_fingerprint

    directory, commit = resolve_model_dir(args.model, args.revision)
    out = {"model": args.model, "commit": commit, "path": str(directory)}
    out["weights"] = weights_fingerprint(directory).to_dict(include_leaves=args.leaves)
    try:
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(str(directory))
        out["tokenizer"] = tokenizer_fingerprint(tok, directory)
    except Exception as exc:
        out["tokenizer"] = None
        out["note"] = f"tokenizer not fingerprinted: {exc}"
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    w = out["weights"]
    print(f"model          {args.model}" + (f"@{commit}" if commit else ""))
    print(f"weights root   {w['root']}")
    print(f"tensors        {w['tensors']} ({w['bytes']:,} bytes, {w['format']})")
    if out["tokenizer"]:
        t = out["tokenizer"]
        print(f"vocab          {t['vocab']} ({t['vocab_size']} tokens)")
        print(f"tokenizer.json {t['tokenizer_json']}")
        print(f"chat template  {t['chat_template']}")
    elif out.get("note"):
        print(out["note"])
    if args.leaves:
        for name, h in sorted(w["leaves"].items()):
            print(f"{h}  {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from modeldiffr.fingerprint import UnsupportedWeightsError

    handlers: dict = {}
    args = _build_parser(handlers).parse_args(argv)
    try:
        if args.command in handlers:
            return handlers[args.command](args)
        if args.command == "suites":
            return _cmd_suites()
        if args.command == "audit":
            return _cmd_audit(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "tasks":
            return _cmd_tasks()
        if args.command == "power":
            return _cmd_power(args)
        if args.command == "refusal-eval":
            return _cmd_refusal_eval(args)
        if args.command == "fingerprint":
            return _cmd_fingerprint(args)
    except UnsupportedWeightsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except MissingDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ModeldiffrError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
