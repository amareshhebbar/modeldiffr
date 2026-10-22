from pathlib import Path

SIGNATURE = "model.sig"


def _check(side, status, detail):
    return {"name": f"{side}_model_signature", "status": status, "detail": detail}


def check_model_signature(
    side: str,
    model_dir: str | Path,
    identity: str | None = None,
    issuer: str | None = None,
    staging: bool = False,
    public_key: str | None = None,
    module=None,
) -> dict | None:
    d = Path(model_dir)
    sig = d / SIGNATURE
    if not sig.exists():
        return None
    if module is None:
        try:
            import model_signing as module
        except ImportError:
            return _check(
                side, "skip", f"{SIGNATURE} present, pip install model-signing to check it"
            )
    config = module.verifying.Config()
    if public_key:
        config = config.use_elliptic_key_verifier(public_key=public_key)
    elif identity and issuer:
        config = config.use_sigstore_verifier(
            identity=identity, oidc_issuer=issuer, use_staging=staging
        )
    else:
        return _check(side, "skip", f"{SIGNATURE} present, pass --identity and --issuer")
    config = config.set_ignore_unsigned_files(True)
    try:
        config.verify(d, sig)
    except Exception as exc:
        return _check(side, "fail", f"OpenSSF model signature did not verify: {exc}")
    return _check(side, "pass", "OpenSSF model signature verified")
