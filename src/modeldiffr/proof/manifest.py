from modeldiffr.proof.canonical import canonical_json, object_hash, sha256_hex
from modeldiffr.proof.merkle import leaf_hash, root_hex

MANIFEST_SCHEMA = "modeldiffr.manifest/1"
AUDIT_ID_PREFIX = "mdr1:"
SECTIONS = ("capability", "over_refusal")


def suite_leaves(suite) -> list[bytes]:
    leaves = []
    for item in suite.capability:
        leaves.append(
            {
                "kind": "capability",
                "question": item.question,
                "choices": list(item.choices),
                "answer": item.answer,
            }
        )
    for prompt in suite.benign_prompts:
        leaves.append({"kind": "over_refusal", "prompt": prompt})
    for text in suite.neutral_texts:
        leaves.append({"kind": "divergence", "text": text})
    return [leaf_hash(canonical_json(x)) for x in leaves]


def suite_root(suite) -> str:
    return root_hex(suite_leaves(suite))


def suite_entry(suite) -> dict:
    return {
        "name": suite.name,
        "root": suite_root(suite),
        "items": len(suite.capability) + len(suite.benign_prompts) + len(suite.neutral_texts),
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
    suite,
    settings: dict,
    version: str,
) -> dict:
    return {
        "schema": MANIFEST_SCHEMA,
        "base": model_entry(base_meta, base_fp),
        "derivative": model_entry(derivative_meta, derivative_fp),
        "suite": suite_entry(suite),
        "settings": dict(settings),
        "code": {"package": "modeldiffr", "version": version},
    }


def audit_id(manifest: dict) -> str:
    return AUDIT_ID_PREFIX + sha256_hex(canonical_json(manifest))


def result_leaves(items: dict) -> list[bytes]:
    leaves = []
    for section in SECTIONS:
        for model in ("base", "derivative"):
            for index, row in enumerate(items[section][model]):
                record = {"section": section, "model": model, "index": index, "row": row}
                leaves.append(leaf_hash(canonical_json(record)))
    for index, row in enumerate(items.get("divergence", [])):
        record = {"section": "divergence", "model": "pair", "index": index, "row": row}
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
