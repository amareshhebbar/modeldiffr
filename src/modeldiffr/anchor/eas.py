import os

from modeldiffr.errors import ModeldiffrError

EAS_ADDRESS = "0x4200000000000000000000000000000000000021"
SCHEMA_REGISTRY = "0x4200000000000000000000000000000000000020"
SCHEMA = "bytes32 auditId,bytes32 resultsRoot,bytes32 statementSha256,string verdict"
ZERO32 = b"\x00" * 32
CHAINS = {"base": 8453, "base-sepolia": 84532, "optimism": 10, "optimism-sepolia": 11155420}

EAS_ABI = [
    {
        "name": "attest",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {
                "name": "request",
                "type": "tuple",
                "components": [
                    {"name": "schema", "type": "bytes32"},
                    {
                        "name": "data",
                        "type": "tuple",
                        "components": [
                            {"name": "recipient", "type": "address"},
                            {"name": "expirationTime", "type": "uint64"},
                            {"name": "revocable", "type": "bool"},
                            {"name": "refUID", "type": "bytes32"},
                            {"name": "data", "type": "bytes"},
                            {"name": "value", "type": "uint256"},
                        ],
                    },
                ],
            }
        ],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
    {
        "name": "getAttestation",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "uid", "type": "bytes32"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "uid", "type": "bytes32"},
                    {"name": "schema", "type": "bytes32"},
                    {"name": "time", "type": "uint64"},
                    {"name": "expirationTime", "type": "uint64"},
                    {"name": "revocationTime", "type": "uint64"},
                    {"name": "refUID", "type": "bytes32"},
                    {"name": "recipient", "type": "address"},
                    {"name": "attester", "type": "address"},
                    {"name": "revocable", "type": "bool"},
                    {"name": "data", "type": "bytes"},
                ],
            }
        ],
    },
]


class EASError(ModeldiffrError):
    pass


def _b32(value: str) -> bytes:
    h = value.split(":", 1)[-1]
    raw = bytes.fromhex(h)
    if len(raw) != 32:
        raise EASError(f"{value} is not a 32 byte hash")
    return raw


def encode_data(audit_id: str, results_root: str, statement_sha256: str, verdict: str) -> bytes:
    text = verdict.encode("utf-8")
    padded = text + b"\x00" * (-len(text) % 32)
    head = _b32(audit_id) + _b32(results_root) + _b32(statement_sha256) + (128).to_bytes(32, "big")
    return head + len(text).to_bytes(32, "big") + padded


def decode_data(data: bytes) -> dict:
    if len(data) < 160:
        raise EASError("attestation data is too short")
    offset = int.from_bytes(data[96:128], "big")
    n = int.from_bytes(data[offset : offset + 32], "big")
    return {
        "audit_id": "mdr1:" + data[0:32].hex(),
        "results_root": "sha256:" + data[32:64].hex(),
        "statement_sha256": "sha256:" + data[64:96].hex(),
        "verdict": data[offset + 32 : offset + 32 + n].decode("utf-8"),
    }


def verdict_text(report: dict) -> str:
    v = report["verdict"]
    return "changed: " + ", ".join(v["changed"]) if v["changed"] else "no significant change"


def payload(report: dict) -> bytes:
    return encode_data(
        report["audit_id"],
        report["proof"]["results_root"],
        report["proof"]["statement_sha256"],
        verdict_text(report),
    )


def _web3(rpc: str):
    try:
        from web3 import Web3
    except ImportError as exc:
        raise EASError('on chain anchoring needs web3: pip install "modeldiffr[anchor]"') from exc
    w3 = Web3(Web3.HTTPProvider(rpc))
    return Web3, w3


def attest(
    report: dict, schema_uid: str, rpc: str, key_env: str = "MODELDIFFR_ETH_KEY", web3_module=None
) -> dict:
    key = os.environ.get(key_env)
    if not key:
        raise EASError(f"set {key_env} to the private key of the attesting account")
    Web3, w3 = web3_module or _web3(rpc)
    account = w3.eth.account.from_key(key)
    contract = w3.eth.contract(address=Web3.to_checksum_address(EAS_ADDRESS), abi=EAS_ABI)
    request = (
        bytes.fromhex(schema_uid.removeprefix("0x")),
        ("0x0000000000000000000000000000000000000000", 0, False, ZERO32, payload(report), 0),
    )
    tx = contract.functions.attest(request).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": w3.eth.chain_id,
        }
    )
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    uid = None
    for log in receipt.get("logs", []):
        data = log.get("data")
        if (
            str(log.get("address", "")).lower() == EAS_ADDRESS.lower()
            and data
            and len(bytes(data)) >= 32
        ):
            uid = "0x" + bytes(data)[:32].hex()
    return {
        "chain_id": w3.eth.chain_id,
        "contract": EAS_ADDRESS,
        "schema": schema_uid,
        "tx": "0x" + bytes(tx_hash).hex().removeprefix("0x"),
        "uid": uid,
        "attester": account.address,
    }


def fetch(uid: str, rpc: str, web3_module=None) -> dict:
    Web3, w3 = web3_module or _web3(rpc)
    contract = w3.eth.contract(address=Web3.to_checksum_address(EAS_ADDRESS), abi=EAS_ABI)
    att = contract.functions.getAttestation(bytes.fromhex(uid.removeprefix("0x"))).call()
    return {
        "time": att[2],
        "revoked": bool(att[4]),
        "attester": att[7],
        **decode_data(bytes(att[9])),
    }


def check(report: dict, record: dict, rpc: str, web3_module=None) -> tuple[bool, str]:
    got = fetch(record["uid"], rpc, web3_module)
    if got["revoked"]:
        return False, "the attestation was revoked"
    for key in ("audit_id", "results_root", "statement_sha256"):
        want = report["audit_id"] if key == "audit_id" else report["proof"][key]
        if got[key] != want:
            return False, f"on chain {key} does not match the report"
    return True, f"attested on chain {record.get('chain_id')} by {got['attester']}"
