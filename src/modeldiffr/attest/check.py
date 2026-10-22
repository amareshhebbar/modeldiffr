import json
from pathlib import Path

from modeldiffr.attest.statement import check_binding

DSSE_FILE = "report.dsse.json"
SIGSTORE_FILE = "report.sigstore.json"
OTS_FILE = "statement.sha256.ots"
ANCHORS_FILE = "anchors.json"


def _c(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def _dsse(report, path, key):
    from modeldiffr.attest.keys import SigningError, verify_envelope

    if not key:
        return _c("signature", "skip", f"{DSSE_FILE} present, pass --key PUBLIC_KEY to check it")
    try:
        statement = verify_envelope(json.loads(path.read_text()), key)
    except (SigningError, ValueError, KeyError) as exc:
        return _c("signature", "fail", str(exc))
    problems = check_binding(statement, report)
    detail = "; ".join(problems) or f"signed with {Path(key).name}"
    return _c("signature", "fail" if problems else "pass", detail)


def _sigstore(report, path, identity, issuer, staging):
    from modeldiffr.attest.keys import SigningError

    if not (identity and issuer):
        return _c(
            "sigstore", "skip", f"{SIGSTORE_FILE} present, pass --identity and --issuer to check it"
        )
    from modeldiffr.attest.sigstore_backend import verify_sigstore

    try:
        statement = verify_sigstore(path.read_text(), identity, issuer, staging)
    except SigningError as exc:
        return _c("sigstore", "fail", str(exc))
    problems = check_binding(statement, report)
    detail = "; ".join(problems) or f"signed by {identity}, logged in Rekor"
    return _c("sigstore", "fail" if problems else "pass", detail)


def check_attestations(
    report: dict, directory, key=None, identity=None, issuer=None, staging=False, rpc=None
) -> list[dict]:
    if directory is None:
        return []
    d = Path(directory)
    out = []
    if (d / DSSE_FILE).exists():
        out.append(_dsse(report, d / DSSE_FILE, key))
    if (d / SIGSTORE_FILE).exists():
        out.append(_sigstore(report, d / SIGSTORE_FILE, identity, issuer, staging))
    if (d / OTS_FILE).exists():
        from modeldiffr.anchor.ots import AnchorError, check

        try:
            ok, detail = check(d / OTS_FILE, report["proof"]["statement_sha256"])
            out.append(_c("opentimestamps", "pass" if ok else "fail", detail))
        except AnchorError as exc:
            out.append(_c("opentimestamps", "skip", str(exc)))
    if (d / ANCHORS_FILE).exists():
        from modeldiffr.anchor.eas import EASError, check

        for rec in json.loads((d / ANCHORS_FILE).read_text()).get("eas", []):
            if not rpc:
                out.append(
                    _c(
                        "eas",
                        "skip",
                        f"attestation {rec.get('uid')} recorded, pass --rpc to check it",
                    )
                )
                continue
            try:
                ok, detail = check(report, rec, rpc)
                out.append(_c("eas", "pass" if ok else "fail", detail))
            except EASError as exc:
                out.append(_c("eas", "fail", str(exc)))
    return out
