import json
from pathlib import Path

from modeldiffr.interp.model import InterpError
from modeldiffr.proof.canonical import canonical_json
from modeldiffr.proof.merkle import leaf_hash, root_hex


def builtin_texts() -> list[str]:
    from modeldiffr.suites import QUICK

    texts = list(QUICK.neutral_texts) + list(QUICK.benign_prompts)
    for item in QUICK.capability:
        texts.append(f"Question: {item.question}\nAnswer: {item.choices[item.answer]}")
    return texts


def _read_file(path: Path, field: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        out = []
        for line in text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            value = row.get(field) if isinstance(row, dict) else row
            if isinstance(value, str) and value.strip():
                out.append(value)
        return out
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _read_hub(spec: str, field: str, limit: int) -> list[str]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise InterpError('Hub corpora need datasets: pip install "modeldiffr[tasks]"') from exc
    parts = spec.split(":")
    name = parts[0]
    config = parts[1] if len(parts) > 2 and parts[1] else None
    split = parts[-1] if len(parts) > 1 else "train"
    ds = load_dataset(name, config, split=split, streaming=True)
    out = []
    for row in ds:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            out.append(value)
        if len(out) >= limit:
            break
    return out


def load_corpus(source: str | None, limit: int = 2000, field: str = "text") -> list[str]:
    if source in (None, "", "builtin"):
        texts = builtin_texts()
    elif source.startswith("hf:"):
        texts = _read_hub(source[3:], field, limit)
    else:
        p = Path(source)
        if not p.exists():
            raise InterpError(
                f"corpus {source} not found; pass a .jsonl or .txt file, hf:NAME:SPLIT"
            )
        texts = _read_file(p, field)
    if not texts:
        raise InterpError(f"corpus {source or 'builtin'} has no texts")
    return texts[:limit]


def corpus_root(texts: list[str]) -> str:
    return root_hex(
        [leaf_hash(canonical_json({"index": i, "text": t})) for i, t in enumerate(texts)]
    )
