import json
import sys
from pathlib import Path


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sign_report(report_path, key=None, sigstore=False, staging=False, token=None) -> list[Path]:
    from modeldiffr.attest import build_statement

    report_path = Path(report_path)
    report = _load(report_path)
    statement = build_statement(report)
    written = []
    if key:
        from modeldiffr.attest.keys import sign_statement

        env = sign_statement(statement, key)
        out = report_path.parent / "report.dsse.json"
        out.write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
        written.append(out)
    if sigstore:
        from modeldiffr.attest.sigstore_backend import sign_sigstore

        bundle = sign_sigstore(statement, identity_token=token, staging=staging)
        out = report_path.parent / "report.sigstore.json"
        out.write_text(bundle, encoding="utf-8")
        written.append(out)
    return written


def register(sub) -> dict:
    keygen = sub.add_parser("keygen", help="Create an Ed25519 key pair for signing reports.")
    keygen.add_argument("--out", default="keys")
    keygen.add_argument("--name", default="modeldiffr")

    sign = sub.add_parser("sign", help="Sign a report as an in toto attestation.")
    sign.add_argument("report")
    sign.add_argument("--key", default=None, help="Ed25519 private key from modeldiffr keygen.")
    sign.add_argument("--sigstore", action="store_true", help="Keyless signing with Sigstore.")
    sign.add_argument("--staging", action="store_true", help="Use the Sigstore staging instance.")
    sign.add_argument(
        "--identity-token", default=None, help="OIDC token, detected in CI otherwise."
    )

    anchor = sub.add_parser("anchor", help="Timestamp a report publicly.")
    asub = anchor.add_subparsers(dest="anchor_command", required=True)
    ots = asub.add_parser("ots", help="Timestamp with OpenTimestamps (Bitcoin).")
    ots.add_argument("report")
    up = asub.add_parser("upgrade", help="Complete a pending OpenTimestamps proof.")
    up.add_argument("report")
    eas = asub.add_parser("eas", help="Attest on chain with the Ethereum Attestation Service.")
    eas.add_argument("report")
    eas.add_argument("--schema", required=True, help="Registered EAS schema UID.")
    eas.add_argument(
        "--rpc", required=True, help="JSON RPC endpoint of the chain, for example Base."
    )
    eas.add_argument("--key-env", default="MODELDIFFR_ETH_KEY")

    commit = sub.add_parser("commit", help="Commit to a private JSONL suite by its Merkle root.")
    commit.add_argument("file")
    commit.add_argument("--out", default=None)
    reveal = sub.add_parser("reveal", help="Check a revealed JSONL suite against its commitment.")
    reveal.add_argument("file")
    reveal.add_argument("--commitment", required=True)

    bom = sub.add_parser("bom", help="Export an AI bill of materials for a report.")
    bom.add_argument("report")
    bom.add_argument("--format", choices=["cyclonedx", "spdx"], default="cyclonedx")
    bom.add_argument("--out", default=None)

    hub = sub.add_parser("hub", help="Publish a report to a Hugging Face model repository.")
    hsub = hub.add_subparsers(dest="hub_command", required=True)
    push = hsub.add_parser("push", help="Upload the report folder and print a model card badge.")
    push.add_argument("report_dir")
    push.add_argument("--repo", required=True)
    badge = sub.add_parser("badge", help="Print a model card badge for a report.")
    badge.add_argument("report")
    badge.add_argument("--url", required=True)
    return {
        "keygen": _keygen,
        "sign": _sign,
        "anchor": _anchor,
        "commit": _commit,
        "reveal": _reveal,
        "bom": _bom,
        "hub": _hub,
        "badge": _badge,
    }


def _keygen(args) -> int:
    from modeldiffr.attest.keys import generate

    priv, pub = generate(args.out, args.name)
    print(f"private key {priv}  (keep it secret)")
    print(f"public key  {pub}   (publish it so others can verify)")
    return 0


def _sign(args) -> int:
    if not args.key and not args.sigstore:
        print("error: pass --key PRIVATE_KEY or --sigstore", file=sys.stderr)
        return 2
    for path in sign_report(
        args.report, args.key, args.sigstore, args.staging, args.identity_token
    ):
        print(f"wrote {path}")
    return 0


def _anchor(args) -> int:
    report_path = Path(args.report)
    report = _load(report_path)
    if args.anchor_command == "ots":
        from modeldiffr.anchor.ots import stamp

        print(f"wrote {stamp(report_path.parent, report['proof']['statement_sha256'])}")
        print("the Bitcoin attestation completes in a few hours: modeldiffr anchor upgrade REPORT")
        return 0
    if args.anchor_command == "upgrade":
        from modeldiffr.anchor.ots import upgrade

        print(upgrade(report_path.parent / "statement.sha256.ots"))
        return 0
    from modeldiffr.anchor.eas import attest

    record = attest(report, args.schema, args.rpc, args.key_env)
    anchors_path = report_path.parent / "anchors.json"
    anchors = _load(anchors_path) if anchors_path.exists() else {}
    anchors.setdefault("eas", []).append(record)
    anchors_path.write_text(json.dumps(anchors, indent=2) + "\n", encoding="utf-8")
    print(f"attestation {record['uid']} in transaction {record['tx']}")
    return 0


def _commit(args) -> int:
    from modeldiffr.anchor.commit import commit

    c = commit(args.file)
    out = Path(args.out or f"{args.file}.commitment.json")
    out.write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")
    print(f"root {c['root']} over {c['items']} items, wrote {out}")
    print("publish the commitment now and keep the file private until you reveal it")
    return 0


def _reveal(args) -> int:
    from modeldiffr.anchor.commit import reveal

    ok, detail = reveal(args.file, _load(args.commitment))
    print(("PASS " if ok else "FAIL ") + detail)
    return 0 if ok else 4


def _bom(args) -> int:
    from modeldiffr.integrations.bom import cyclonedx, spdx

    report = _load(args.report)
    doc = cyclonedx(report) if args.format == "cyclonedx" else spdx(report)
    text = json.dumps(doc, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text, end="")
    return 0


def _hub(args) -> int:
    from modeldiffr.integrations.hub import push

    d = Path(args.report_dir)
    result = push(d, args.repo, _load(d / "report.json"))
    print(f"uploaded {', '.join(result['files'])} to {result['url']}")
    print("add this to the model card:")
    print(result["badge"])
    return 0


def _badge(args) -> int:
    from modeldiffr.integrations.hub import badge

    print(badge(_load(args.report), args.url))
    return 0
