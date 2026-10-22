import json
from pathlib import Path

from modeldiffr.proof.canonical import canonical_json, sha256_hex

ALGORITHM = "modeldiffr.tokenizer/1"
_SPECIAL = ("bos_token", "eos_token", "pad_token", "unk_token")


def _h(value) -> str:
    return "sha256:" + sha256_hex(canonical_json(value))


def template_hash(template) -> str | None:
    if not template:
        return None
    if isinstance(template, dict):
        return _h(template)
    return "sha256:" + sha256_hex(str(template).encode("utf-8"))


def tokenizer_fingerprint(tokenizer, model_dir: str | Path | None = None) -> dict:
    vocab = sorted(tokenizer.get_vocab().items(), key=lambda kv: (kv[1], kv[0]))
    special = {k: getattr(tokenizer, k, None) for k in _SPECIAL}
    special = {k: (str(v) if v is not None else None) for k, v in special.items()}
    added = sorted(str(t) for t in (getattr(tokenizer, "additional_special_tokens", None) or []))
    out = {
        "algorithm": ALGORITHM,
        "vocab": _h({"vocab": [[t, i] for t, i in vocab], "added": added}),
        "vocab_size": len(vocab),
        "special_tokens": special,
        "chat_template": template_hash(getattr(tokenizer, "chat_template", None)),
        "tokenizer_json": None,
    }
    if model_dir is not None:
        p = Path(model_dir) / "tokenizer.json"
        if p.exists():
            try:
                out["tokenizer_json"] = _h(json.loads(p.read_text(encoding="utf-8")))
            except (ValueError, UnicodeDecodeError):
                out["tokenizer_json"] = "sha256:" + sha256_hex(p.read_bytes())
    return out
