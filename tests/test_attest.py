import json
import os
import stat
import sys
import types

import pytest

from modeldiffr.anchor import commit as commit_mod
from modeldiffr.anchor import eas
from modeldiffr.attest import build_statement, check_binding
from modeldiffr.attest.dsse import open_envelope, pae
from modeldiffr.audit import run_audit
from modeldiffr.cli import main
from modeldiffr.integrations.bom import cyclonedx, spdx
from modeldiffr.integrations.hub import badge, parse_model_ref, push
from modeldiffr.proof.verify import verify_file
from modeldiffr.report import write_reports
from modeldiffr.suites import QUICK

pytest.importorskip("cryptography")


@pytest.fixture
def report_dir(fp_backend, tmp_path):
    base = fp_backend("base")
    deriv = fp_backend(
        "deriv", correct=False, leaves={"layer.0.weight": "a" * 64, "layer.1.weight": "c" * 64}
    )
    report = run_audit(base, deriv, QUICK, n_resamples=200)
    path, _ = write_reports(report, tmp_path / "out")
    return path.parent


@pytest.fixture
def keys(tmp_path):
    from modeldiffr.attest.keys import generate

    return generate(tmp_path / "keys", "test")


def load(p):
    return json.loads(p.read_text())


def statuses(result):
    return {c["name"]: c["status"] for c in result["checks"]}


def test_pae_matches_the_dsse_spec():
    got = pae("application/vnd.in-toto+json", b"hello")
    assert got == b"DSSEv1 28 application/vnd.in-toto+json 5 hello"


def test_statement_subjects_and_binding(report_dir):
    report = load(report_dir / "report.json")
    st = build_statement(report)
    names = [s["name"] for s in st["subject"]]
    assert names == ["base:base", "derivative:deriv", "modeldiffr:audit"]
    assert st["subject"][-1]["digest"]["sha256"] == report["audit_id"].split(":")[1]
    assert check_binding(st, report) == []
    st["predicate"]["results_root"] = "sha256:" + "0" * 64
    assert check_binding(st, report) == ["signed results_root does not match the report"]


def test_keygen_writes_private_key_with_owner_only_mode(keys):
    priv, pub = keys
    assert stat.S_IMODE(os.stat(priv).st_mode) == 0o600
    assert pub.read_text().startswith("-----BEGIN PUBLIC KEY-----")


def test_sign_then_verify_passes(report_dir, keys):
    priv, pub = keys
    assert main(["sign", str(report_dir / "report.json"), "--key", str(priv)]) == 0
    env = load(report_dir / "report.dsse.json")
    assert env["payloadType"] == "application/vnd.in-toto+json"
    assert env["signatures"][0]["keyid"].startswith("ed25519:")
    statement = json.loads(open_envelope(env)[1])
    assert statement["predicate"]["audit_id"] == load(report_dir / "report.json")["audit_id"]
    result = verify_file(report_dir / "report.json", key=str(pub))
    assert result["ok"]
    assert statuses(result)["signature"] == "pass"


def test_signature_is_skipped_without_a_public_key(report_dir, keys):
    priv, _ = keys
    main(["sign", str(report_dir / "report.json"), "--key", str(priv)])
    result = verify_file(report_dir / "report.json")
    assert result["ok"]
    assert statuses(result)["signature"] == "skip"


def test_wrong_key_fails(report_dir, keys, tmp_path):
    from modeldiffr.attest.keys import generate

    priv, _ = keys
    _, other = generate(tmp_path / "other", "other")
    main(["sign", str(report_dir / "report.json"), "--key", str(priv)])
    result = verify_file(report_dir / "report.json", key=str(other))
    assert not result["ok"]
    assert statuses(result)["signature"] == "fail"


def test_tampered_envelope_fails(report_dir, keys):
    import base64

    priv, pub = keys
    main(["sign", str(report_dir / "report.json"), "--key", str(priv)])
    p = report_dir / "report.dsse.json"
    env = load(p)
    st = json.loads(base64.b64decode(env["payload"]))
    st["predicate"]["verdict"]["any_change"] = not st["predicate"]["verdict"]["any_change"]
    env["payload"] = base64.b64encode(json.dumps(st).encode()).decode()
    p.write_text(json.dumps(env))
    result = verify_file(report_dir / "report.json", key=str(pub))
    assert statuses(result)["signature"] == "fail"


def test_signature_from_another_report_fails_binding(report_dir, keys, fp_backend, tmp_path):
    priv, pub = keys
    other = run_audit(fp_backend("x"), fp_backend("y"), QUICK, n_resamples=200)
    other_path, _ = write_reports(other, tmp_path / "other_report")
    main(["sign", str(other_path), "--key", str(priv)])
    (report_dir / "report.dsse.json").write_text(
        (other_path.parent / "report.dsse.json").read_text()
    )
    result = verify_file(report_dir / "report.json", key=str(pub))
    check = next(c for c in result["checks"] if c["name"] == "signature")
    assert check["status"] == "fail"
    assert "audit_id" in check["detail"]


def test_audit_sign_key_flag(fp_backend, keys, tmp_path, monkeypatch):
    priv, pub = keys
    from modeldiffr import cli

    monkeypatch.setattr(
        cli, "_side_backend", lambda args, side, model, rev: fp_backend(model, correct=True)
    )
    out = tmp_path / "audit"
    code = main(["audit", "b", "d", "--out", str(out), "--sign-key", str(priv)])
    assert code == 0
    assert (out / "report.dsse.json").exists()
    assert verify_file(out / "report.json", key=str(pub))["ok"]


def test_sign_requires_a_method(report_dir, capsys):
    assert main(["sign", str(report_dir / "report.json")]) == 2
    assert "--sigstore" in capsys.readouterr().err


def test_sigstore_sign_builds_the_same_statement(report_dir, monkeypatch):
    calls = {}

    class Builder:
        def subjects(self, s):
            calls["subjects"] = s
            return self

        def predicate_type(self, t):
            calls["type"] = t
            return self

        def predicate(self, p):
            calls["predicate"] = p
            return self

        def build(self):
            return "stmt"

    class Signer:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def sign_dsse(self, stmt):
            calls["signed"] = stmt
            return types.SimpleNamespace(to_json=lambda: '{"bundle": true}')

    class Ctx:
        @classmethod
        def from_trust_config(cls, trust):
            calls["trust"] = trust
            return cls()

        def signer(self, token):
            calls["token"] = token
            return Signer()

    fake = types.ModuleType("sigstore")
    dsse_mod = types.ModuleType("sigstore.dsse")
    dsse_mod.StatementBuilder = Builder
    dsse_mod.Subject = lambda name, digest: (name, digest["sha256"])
    models = types.ModuleType("sigstore.models")
    models.ClientTrustConfig = types.SimpleNamespace(
        staging=lambda: "staging", production=lambda: "production"
    )
    oidc = types.ModuleType("sigstore.oidc")
    oidc.IdentityToken = lambda raw: f"token:{raw}"
    oidc.Issuer = None
    oidc.detect_credential = lambda: None
    sign = types.ModuleType("sigstore.sign")
    sign.SigningContext = Ctx
    fake.dsse = dsse_mod
    for name, mod in {
        "sigstore": fake,
        "sigstore.dsse": dsse_mod,
        "sigstore.models": models,
        "sigstore.oidc": oidc,
        "sigstore.sign": sign,
    }.items():
        monkeypatch.setitem(sys.modules, name, mod)

    code = main(
        [
            "sign",
            str(report_dir / "report.json"),
            "--sigstore",
            "--staging",
            "--identity-token",
            "abc",
        ]
    )
    assert code == 0
    report = load(report_dir / "report.json")
    st = build_statement(report)
    assert calls["trust"] == "staging"
    assert calls["token"] == "token:abc"
    assert calls["type"] == st["predicateType"]
    assert calls["predicate"] == st["predicate"]
    assert [s[0] for s in calls["subjects"]] == [s["name"] for s in st["subject"]]
    assert load(report_dir / "report.sigstore.json") == {"bundle": True}


def test_sigstore_bundle_needs_identity_to_check(report_dir):
    (report_dir / "report.sigstore.json").write_text("{}")
    result = verify_file(report_dir / "report.json")
    assert statuses(result)["sigstore"] == "skip"


def write_fake_ots(bin_dir, bitcoin):
    attestation = (
        "verify BitcoinBlockHeaderAttestation(915000)" if bitcoin else "verify PendingAttestation"
    )
    bin_dir.mkdir()
    script = bin_dir / "ots"
    script.write_text(
        f"""#!{sys.executable}
import hashlib, sys
cmd, path = sys.argv[1], sys.argv[2]
if cmd == "stamp":
    data = open(path, "rb").read()
    open(path + ".ots", "w").write(hashlib.sha256(data).hexdigest())
elif cmd == "upgrade":
    print("Success! Timestamp complete")
elif cmd == "info":
    digest = open(path).read().strip()
    print("File sha256 hash: " + digest)
    print("Timestamp:")
    print({attestation!r})
"""
    )
    script.chmod(0o755)


@pytest.mark.parametrize("bitcoin", [False, True])
def test_opentimestamps_round_trip(report_dir, tmp_path, monkeypatch, bitcoin):
    write_fake_ots(tmp_path / "bin", bitcoin)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    assert main(["anchor", "ots", str(report_dir / "report.json")]) == 0
    report = load(report_dir / "report.json")
    digest = (report_dir / "statement.sha256").read_text().strip()
    assert "sha256:" + digest == report["proof"]["statement_sha256"]
    result = verify_file(report_dir / "report.json")
    check = next(c for c in result["checks"] if c["name"] == "opentimestamps")
    assert check["status"] == "pass"
    assert ("Bitcoin block" if bitcoin else "waiting") in check["detail"]


def test_opentimestamps_for_another_statement_fails(report_dir, tmp_path, monkeypatch):
    write_fake_ots(tmp_path / "bin", True)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    (report_dir / "statement.sha256.ots").write_text("0" * 64)
    result = verify_file(report_dir / "report.json")
    assert statuses(result)["opentimestamps"] == "fail"


def test_missing_ots_client_skips(report_dir, monkeypatch):
    monkeypatch.setenv("PATH", "")
    (report_dir / "statement.sha256.ots").write_text("x")
    result = verify_file(report_dir / "report.json")
    assert statuses(result)["opentimestamps"] == "skip"


def test_eas_encoding_round_trip_and_abi_compatibility():
    a, r, s = "mdr1:" + "11" * 32, "sha256:" + "22" * 32, "sha256:" + "33" * 32
    data = eas.encode_data(a, r, s, "changed: mmlu_accuracy")
    assert eas.decode_data(data) == {
        "audit_id": a,
        "results_root": r,
        "statement_sha256": s,
        "verdict": "changed: mmlu_accuracy",
    }
    eth_abi = pytest.importorskip("eth_abi")
    want = eth_abi.encode(
        ["bytes32", "bytes32", "bytes32", "string"],
        [
            bytes.fromhex("11" * 32),
            bytes.fromhex("22" * 32),
            bytes.fromhex("33" * 32),
            "changed: mmlu_accuracy",
        ],
    )
    assert data == want


class FakeChain:
    def __init__(self):
        self.store = {}
        self.uid = bytes.fromhex("ab" * 32)
        chain = self

        class Fn:
            def __init__(self, name, args):
                self.name, self.args = name, args

            def build_transaction(self, tx):
                return {"fn": self.name, "args": self.args, **tx}

            def call(self):
                data = chain.store[self.args[0]]
                return (self.args[0], b"", 1700000000, 0, 0, b"", "0xR", "0xA", True, data)

        class Functions:
            def attest(self, request):
                return Fn("attest", (request,))

            def getAttestation(self, uid):
                return Fn("get", (uid,))

        account = types.SimpleNamespace(
            address="0xA",
            sign_transaction=lambda tx: types.SimpleNamespace(raw_transaction=tx),
        )

        def send(raw):
            chain.store[chain.uid] = raw["args"][0][1][4]
            return bytes.fromhex("cd" * 32)

        self.w3 = types.SimpleNamespace(
            eth=types.SimpleNamespace(
                account=types.SimpleNamespace(from_key=lambda k: account),
                contract=lambda address, abi: types.SimpleNamespace(functions=Functions()),
                get_transaction_count=lambda a: 7,
                chain_id=84532,
                send_raw_transaction=send,
                wait_for_transaction_receipt=lambda h: {
                    "logs": [
                        {"address": "0x1234", "data": b"\x00" * 32},
                        {"address": eas.EAS_ADDRESS, "data": chain.uid},
                    ]
                },
            )
        )
        self.module = (types.SimpleNamespace(to_checksum_address=lambda a: a), self.w3)


def test_eas_attest_then_check(report_dir, monkeypatch):
    chain = FakeChain()
    monkeypatch.setenv("MODELDIFFR_ETH_KEY", "0x" + "1" * 64)
    report = load(report_dir / "report.json")
    record = eas.attest(report, "0x" + "ee" * 32, "http://rpc", web3_module=chain.module)
    assert record["uid"] == "0x" + "ab" * 32
    assert record["chain_id"] == 84532
    ok, detail = eas.check(report, record, "http://rpc", web3_module=chain.module)
    assert ok, detail
    other = json.loads(json.dumps(report))
    other["proof"]["results_root"] = "sha256:" + "0" * 64
    ok, detail = eas.check(other, record, "http://rpc", web3_module=chain.module)
    assert not ok and "results_root" in detail


def test_eas_needs_a_key(report_dir, monkeypatch):
    monkeypatch.delenv("MODELDIFFR_ETH_KEY", raising=False)
    with pytest.raises(eas.EASError):
        eas.attest(load(report_dir / "report.json"), "0x" + "ee" * 32, "http://rpc")


def test_eas_record_is_skipped_without_rpc(report_dir):
    (report_dir / "anchors.json").write_text(json.dumps({"eas": [{"uid": "0x01"}]}))
    assert statuses(verify_file(report_dir / "report.json"))["eas"] == "skip"


def test_commit_and_reveal(tmp_path, capsys):
    f = tmp_path / "private.jsonl"
    f.write_text('{"q": "a"}\n{"q": "b"}\n')
    assert main(["commit", str(f)]) == 0
    c = tmp_path / "private.jsonl.commitment.json"
    assert load(c)["items"] == 2
    assert main(["reveal", str(f), "--commitment", str(c)]) == 0
    f.write_text('{"q": "a"}\n{"q": "B"}\n')
    assert main(["reveal", str(f), "--commitment", str(c)]) == 4
    assert "FAIL" in capsys.readouterr().out


def test_commitment_is_independent_of_key_order(tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text('{"x": 1, "y": 2}\n')
    b.write_text('{"y": 2, "x": 1}\n')
    assert commit_mod.rows_root(a) == commit_mod.rows_root(b)


def test_cyclonedx_bom(report_dir):
    report = load(report_dir / "report.json")
    doc = cyclonedx(report)
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.6"
    assert {c["bom-ref"] for c in doc["components"]} == {"base", "derivative"}
    props = {p["name"]: p["value"] for p in doc["metadata"]["properties"]}
    assert props["modeldiffr:audit_id"] == report["audit_id"]
    assert doc == cyclonedx(report)


def test_spdx_bom(report_dir):
    report = load(report_dir / "report.json")
    doc = spdx(report)
    types_ = [e["type"] for e in doc["@graph"]]
    assert types_.count("ai_AIPackage") == 2
    assert "Relationship" in types_


def test_bom_cli_writes_file(report_dir, tmp_path):
    out = tmp_path / "bom.json"
    assert (
        main(["bom", str(report_dir / "report.json"), "--format", "spdx", "--out", str(out)]) == 0
    )
    assert "@context" in load(out)


def test_badge_and_model_refs(report_dir):
    report = load(report_dir / "report.json")
    b = badge(report, "https://example.org/r")
    assert b.startswith("[![Modeldiffr audit](https://img.shields.io/badge/modeldiffr-")
    assert parse_model_ref("https://huggingface.co/org/m/tree/abc") == ("org/m", "abc")
    assert parse_model_ref("org/m") == ("org/m", None)


def test_hub_push_uploads_only_known_files(report_dir, keys):
    priv, _ = keys
    main(["sign", str(report_dir / "report.json"), "--key", str(priv)])
    (report_dir / "secret.txt").write_text("x")
    seen = {}

    class Api:
        def upload_folder(self, **kw):
            seen.update(kw)

    report = load(report_dir / "report.json")
    result = push(report_dir, "org/model", report, api=Api())
    assert seen["repo_id"] == "org/model"
    assert "secret.txt" not in seen["allow_patterns"]
    assert "report.dsse.json" in seen["allow_patterns"]
    assert result["url"].endswith("/report.html")


def test_model_signature_absent_is_ignored(tmp_path):
    from modeldiffr.integrations.model_signing import check_model_signature

    assert check_model_signature("base", tmp_path) is None


def test_model_signature_with_a_real_elliptic_key(tmp_path):
    pytest.importorskip("model_signing")
    pytest.importorskip("OpenSSL")
    import model_signing
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from modeldiffr.integrations.model_signing import check_model_signature

    key = ec.generate_private_key(ec.SECP256R1())
    priv, pub = tmp_path / "k.pem", tmp_path / "k.pub"
    priv.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    pub.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.safetensors").write_bytes(b"weights")
    (model / "config.json").write_text("{}")
    model_signing.signing.Config().use_elliptic_key_signer(private_key=priv).sign(
        model, model / "model.sig"
    )
    ok = check_model_signature("base", model, public_key=str(pub))
    assert ok["status"] == "pass", ok
    (model / "model.safetensors").write_bytes(b"changed")
    bad = check_model_signature("base", model, public_key=str(pub))
    assert bad["status"] == "fail"


def test_model_signature_uses_sigstore_identity(tmp_path):
    from modeldiffr.integrations.model_signing import check_model_signature

    (tmp_path / "model.sig").write_text("{}")
    seen = {}

    class Config:
        def use_sigstore_verifier(self, **kw):
            seen.update(kw)
            return self

        def set_ignore_unsigned_files(self, value):
            return self

        def verify(self, model, sig):
            seen["verified"] = (model, sig)

    module = types.SimpleNamespace(verifying=types.SimpleNamespace(Config=Config))
    got = check_model_signature("derivative", tmp_path, "a@b.c", "https://iss", module=module)
    assert got["status"] == "pass"
    assert seen["identity"] == "a@b.c" and seen["oidc_issuer"] == "https://iss"
    skipped = check_model_signature("derivative", tmp_path, module=module)
    assert skipped["status"] == "skip"
