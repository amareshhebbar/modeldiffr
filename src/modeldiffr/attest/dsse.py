import base64
import json

from modeldiffr.attest.statement import PAYLOAD_TYPE


def pae(payload_type: str, payload: bytes) -> bytes:
    t = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(t), t, len(payload), payload)


def payload_bytes(statement: dict) -> bytes:
    return json.dumps(statement, sort_keys=True, separators=(",", ":")).encode("utf-8")


def envelope(statement: dict, sign, keyid: str) -> dict:
    payload = payload_bytes(statement)
    sig = sign(pae(PAYLOAD_TYPE, payload))
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode("ascii")}],
    }


def open_envelope(env: dict) -> tuple[str, bytes, list[dict]]:
    return env["payloadType"], base64.b64decode(env["payload"]), env.get("signatures", [])
