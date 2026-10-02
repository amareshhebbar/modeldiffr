import argparse
import sys

from modeldiffr import __version__
from modeldiffr.backend import MissingDependencyError
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

    sub.add_parser("suites", help="List available suites.")
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
    result = run_audit(
        base, derivative, suite, seed=args.seed, n_resamples=args.resamples, progress=log
    )
    json_path, html_path = write_reports(result, args.out)

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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "suites":
            return _cmd_suites()
        if args.command == "audit":
            return _cmd_audit(args)
    except MissingDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
