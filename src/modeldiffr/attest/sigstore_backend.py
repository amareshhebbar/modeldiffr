import json

from modeldiffr.attest.keys import SigningError


def _sigstore():
    try:
        import sigstore  # noqa: F401
    except ImportError as exc:
        raise SigningError('Sigstore signing needs: pip install "modeldiffr[sign]"') from exc


def sign_sigstore(statement: dict, identity_token: str | None = None, staging: bool = False) -> str:
    _sigstore()
    from sigstore import dsse
    from sigstore.models import ClientTrustConfig
    from sigstore.oidc import IdentityToken, Issuer, detect_credential
    from sigstore.sign import SigningContext

    trust = ClientTrustConfig.staging() if staging else ClientTrustConfig.production()
    raw = identity_token or detect_credential()
    if raw:
        token = IdentityToken(raw)
    else:
        token = Issuer(trust.signing_config.get_oidc_url()).identity_token()
    subjects = [
        dsse.Subject(name=s["name"], digest={"sha256": s["digest"]["sha256"]})
        for s in statement["subject"]
    ]
    stmt = (
        dsse.StatementBuilder()
        .subjects(subjects)
        .predicate_type(statement["predicateType"])
        .predicate(statement["predicate"])
        .build()
    )
    ctx = SigningContext.from_trust_config(trust)
    with ctx.signer(token) as signer:
        bundle = signer.sign_dsse(stmt)
    return bundle.to_json()


def verify_sigstore(bundle_json: str, identity: str, issuer: str, staging: bool = False) -> dict:
    _sigstore()
    from sigstore.models import Bundle
    from sigstore.verify import Verifier, policy

    verifier = Verifier.staging() if staging else Verifier.production()
    bundle = Bundle.from_json(bundle_json)
    try:
        payload_type, payload = verifier.verify_dsse(
            bundle, policy.Identity(identity=identity, issuer=issuer)
        )
    except Exception as exc:
        raise SigningError(f"Sigstore verification failed: {exc}") from exc
    if payload_type != "application/vnd.in-toto+json":
        raise SigningError(f"unexpected payload type {payload_type}")
    return json.loads(payload)
