import argparse
import json
import sys

from modeldiffr import __version__
from modeldiffr.backend import MissingDependencyError
from modeldiffr.checks import TEMPLATE_MODES, ComparabilityError
from modeldiffr.suites import SUITES, get_suite


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="modeldiffr",
        description="Audit what changed between a base LLM and a derivative model.",
    )
    parser.add_argument("--version", action="version", version=f"modeldiffr {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Compare a base model with a derivative model.")
    audit.add_argument("base", help="Base model id or local path.")
    audit.add_argument("derivative", help="Derivative model id or local path.")
    audit.add_argument("--suite", default="quick", choices=sorted(SUITES), help="Evaluation suite.")
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

    sub.add_parser("suites", help="List available suites.")

    verify = sub.add_parser("verify", help="Check that a report is internally consistent.")
    verify.add_argument("report", help="Path to report.json.")
    verify.add_argument(
        "--models",
        action="store_true",
        help="Also download or read both models and check their weights against the report.",
    )
    verify.add_argument("--json", action="store_true", help="Print the result as JSON.")

    fp = sub.add_parser("fingerprint", help="Print content hashes for a model.")
    fp.add_argument("model", help="Model id or local path.")
    fp.add_argument("--revision", default=None)
    fp.add_argument("--leaves", action="store_true", help="Include the hash of every tensor.")
    fp.add_argument("--json", action="store_true", help="Print the result as JSON.")
    return parser


def _cmd_suites() -> int:
    for name, suite in sorted(SUITES.items()):
        print(
            f"{name}: {len(suite.capability)} capability items, "
            f"{len(suite.benign_prompts)} over refusal prompts, "
            f"{len(suite.neutral_texts)} divergence texts"
        )
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from modeldiffr.audit import run_audit
    from modeldiffr.backend import HFBackend
    from modeldiffr.report import write_reports

    def log(message: str) -> None:
        print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)

    suite = get_suite(args.suite)
    log(f"loading base model {args.base}")
    base = HFBackend(args.base, args.device, args.base_revision, args.dtype, args.trust_remote_code)
    log(f"loading derivative model {args.derivative}")
    derivative = HFBackend(
        args.derivative, args.device, args.derivative_revision, args.dtype, args.trust_remote_code
    )
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
        )
    except ComparabilityError as exc:
        for issue in exc.issues:
            print(f"{issue['level']}: {issue['message']}", file=sys.stderr)
        return 3
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
    for m in result["metrics"]:
        flag = "CHANGED" if m["significant"] else "within noise"
        print(
            f"{m['name']:<24} base {m['base_mean']:.4f}  derivative {m['derivative_mean']:.4f}  "
            f"delta {m['delta']:+.4f}  95% CI [{m['ci_low']:+.4f}, {m['ci_high']:+.4f}]  {flag}"
        )
    for note in result["notes"]:
        print(f"note: {note}")
    print(f"\nreport: {html_path}\njson:   {json_path}")

    if args.fail_on_change and result["verdict"]["any_change"]:
        return 1
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from modeldiffr.proof.verify import verify_file

    def log(message: str) -> None:
        print(f"[modeldiffr] {message}", file=sys.stderr, flush=True)

    try:
        result = verify_file(args.report, check_models=args.models, progress=log)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: cannot read report: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"audit id {result['audit_id']}")
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

    args = _build_parser().parse_args(argv)
    try:
        if args.command == "suites":
            return _cmd_suites()
        if args.command == "audit":
            return _cmd_audit(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "fingerprint":
            return _cmd_fingerprint(args)
    except UnsupportedWeightsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except MissingDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
