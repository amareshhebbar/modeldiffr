import json
from datetime import datetime, timezone
from pathlib import Path

from modeldiffr.proof.canonical import canonical_json
from modeldiffr.proof.merkle import leaf_hash, root_hex


def rows_root(path: str | Path) -> tuple[str, int]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    leaves = [leaf_hash(canonical_json({"index": i, "row": r})) for i, r in enumerate(rows)]
    return root_hex(leaves), len(rows)


def commit(path: str | Path) -> dict:
    root, n = rows_root(path)
    return {
        "schema": "modeldiffr.commitment/1",
        "file": Path(path).name,
        "root": root,
        "items": n,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def reveal(path: str | Path, commitment: dict) -> tuple[bool, str]:
    root, n = rows_root(path)
    if root != commitment["root"]:
        return False, f"the file hashes to {root}, not the committed root"
    if n != commitment["items"]:
        return False, "the number of items differs"
    return True, f"{n} items match the commitment made at {commitment['created_at']}"
