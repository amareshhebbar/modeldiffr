import hashlib
from pathlib import Path

from modeldiffr.attest.dsse import envelope, open_envelope, pae
from modeldiffr.errors import ModeldiffrError


class SigningError(ModeldiffrError):
    pass


def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise SigningError(
            'signing needs the cryptography package: pip install "modeldiffr[sign]"'
        ) from exc
    return serialization, ed25519


def keyid(public_raw: bytes) -> str:
    return "ed25519:" + hashlib.sha256(public_raw).hexdigest()[:32]


def generate(directory: str | Path, name: str = "modeldiffr") -> tuple[Path, Path]:
    serialization, ed25519 = _crypto()
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    key = ed25519.Ed25519PrivateKey.generate()
    priv = d / f"{name}.key"
    pub = d / f"{name}.pub"
    if priv.exists() or pub.exists():
        raise SigningError(f"{priv} or {pub} already exists")
    priv.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    priv.chmod(0o600)
    pub.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return priv, pub


def _raw_public(public_key) -> bytes:
    serialization, _ = _crypto()
    return public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def sign_statement(statement: dict, private_key_path: str | Path) -> dict:
    serialization, ed25519 = _crypto()
    key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise SigningError("only Ed25519 keys are supported, create one with modeldiffr keygen")
    return envelope(statement, key.sign, keyid(_raw_public(key.public_key())))


def verify_envelope(env: dict, public_key_path: str | Path) -> dict:
    import json

    serialization, ed25519 = _crypto()
    from cryptography.exceptions import InvalidSignature

    pub = serialization.load_pem_public_key(Path(public_key_path).read_bytes())
    if not isinstance(pub, ed25519.Ed25519PublicKey):
        raise SigningError("only Ed25519 public keys are supported")
    payload_type, payload, sigs = open_envelope(env)
    import base64

    kid = keyid(_raw_public(pub))
    for s in sigs:
        if s.get("keyid") not in (kid, "", None):
            continue
        try:
            pub.verify(base64.b64decode(s["sig"]), pae(payload_type, payload))
            return json.loads(payload)
        except InvalidSignature:
            continue
    raise SigningError("no signature in the envelope verifies with this public key")
