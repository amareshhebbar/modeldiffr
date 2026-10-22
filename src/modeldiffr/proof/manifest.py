from modeldiffr.proof.canonical import canonical_json, object_hash, sha256_hex
from modeldiffr.proof.merkle import leaf_hash, root_hex

MANIFEST_SCHEMA = "modeldiffr.manifest/2"
AUDIT_ID_PREFIX = "mdr1:"


def suite_leaves(loaded) -> list[bytes]:
    from modeldiffr.tasks.base import item_leaf_data

    leaves = []
    for task, items in loaded:
        leaves.append(leaf_hash(canonical_json({"task": task.name, "header": task.entry(items)})))
        leaves += [leaf_hash(item_leaf_data(task.name, it)) for it in items]
    return leaves


def suite_root(loaded) -> str:
    return root_hex(suite_leaves(loaded))


def suite_entry(name: str, loaded) -> dict:
    return {
        "name": name,
        "root": suite_root(loaded),
        "items": sum(len(items) for _, items in loaded),
        "tasks": [task.entry(items) for task, items in loaded],
    }


def model_entry(meta: dict, fp: dict | None) -> dict:
    fp = fp or {}
    tok = fp.get("tokenizer") or {}
    weights = fp.get("weights") or {}
    return {
        "model_id": meta.get("model_id"),
        "revision": meta.get("revision"),
        "commit": fp.get("commit"),
        "weights_root": weights.get("root"),
        "weights_algorithm": weights.get("algorithm"),
        "tokenizer_vocab": tok.get("vocab"),
        "tokenizer_json": tok.get("tokenizer_json"),
        "chat_template": tok.get("chat_template"),
    }


def build_manifest(
    base_meta: dict,
    base_fp: dict | None,
    derivative_meta: dict,
    derivative_fp: dict | None,
    suite: dict,
    settings: dict,
    version: str,
) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "base": model_entry(base_meta, base_fp),
        "derivative": model_entry(derivative_meta, derivative_fp),
        "suite": suite,
        "settings": dict(settings),
        "code": {"package": "modeldiffr", "version": version},
    }


def audit_id(manifest: dict) -> str:
    return AUDIT_ID_PREFIX + sha256_hex(canonical_json(manifest))


def result_leaves(items: dict) -> list[bytes]:
    leaves = []
    for task in sorted(items):
        block = items[task]
        for side in ("base", "derivative", "pair"):
            for index, row in enumerate(block.get(side, [])):
                record = {"task": task, "side": side, "index": index, "row": row}
                leaves.append(leaf_hash(canonical_json(record)))
    return leaves


def results_root(items: dict) -> str:
    return root_hex(result_leaves(items))


def statement(result: dict) -> dict:
    return {
        "audit_id": result["audit_id"],
        "results_root": result["proof"]["results_root"],
        "metrics": result["metrics"],
        "verdict": result["verdict"],
        "comparability": result["comparability"],
        "weights_diff": result.get("weights_diff"),
    }


def statement_hash(result: dict) -> str:
    return object_hash(statement(result))
