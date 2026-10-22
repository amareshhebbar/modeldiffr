import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from modeldiffr.proof.canonical import canonical_json, object_hash, sha256_hex

PREFIXES = {
    "modeldiffr.features/1": "mdrf1:",
    "modeldiffr.causal/1": "mdrc1:",
    "modeldiffr.scan/1": "mdrs1:",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_hash(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def finalize(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("result_sha256", None)
    doc["id"] = PREFIXES[doc["schema"]] + sha256_hex(canonical_json(doc["manifest"]))
    doc["result_sha256"] = object_hash({k: v for k, v in doc.items() if k != "result_sha256"})
    return doc


def write(doc: dict, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _c(name, ok, detail):
    return {"name": name, "status": "pass" if ok else "fail", "detail": detail}


def verify_artifact(path: str | Path, extra=None) -> dict:
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    schema = doc.get("schema")
    if schema not in PREFIXES:
        return {
            "ok": False,
            "id": doc.get("id"),
            "checks": [_c("schema", False, f"unknown {schema}")],
        }
    checks = []
    want = PREFIXES[schema] + sha256_hex(canonical_json(doc["manifest"]))
    same = want == doc.get("id")
    checks.append(_c("id", same, want if same else f"manifest hashes to {want}"))
    got = object_hash({k: v for k, v in doc.items() if k != "result_sha256"})
    same = got == doc.get("result_sha256")
    checks.append(
        _c("result_hash", same, "results match their hash" if same else "results were changed")
    )
    for name, rec in (doc.get("files") or {}).items():
        fp = p.parent / name
        if not fp.exists():
            checks.append({"name": name, "status": "skip", "detail": "file not next to the json"})
            continue
        same = file_hash(fp) == rec
        checks.append(
            _c(name, same, "matches its hash" if same else "differs from the recorded hash")
        )
    if extra:
        checks += extra(doc)
    return {"ok": all(c["status"] != "fail" for c in checks), "id": doc.get("id"), "checks": checks}
