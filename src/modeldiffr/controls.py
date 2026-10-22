import hashlib
import json
import re
import shutil
from pathlib import Path

from modeldiffr.errors import ModeldiffrError

SCHEMA = "modeldiffr.control/1"
KINDS = ("identity", "noise", "scale", "zero", "prune")
CONTROL_FILE = "modeldiffr_control.json"
COPY_SUFFIXES = (".json", ".txt", ".model", ".jinja", ".tiktoken", ".py", ".md")
LINEAR_NAMES = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
    "c_attn",
    "c_proj",
    "c_fc",
    "query_key_value",
    "dense",
    "dense_h_to_4h",
    "dense_4h_to_h",
    "fc1",
    "fc2",
    "out_proj",
)
DEFAULT_MATCH = r"(^|\.)(" + "|".join(LINEAR_NAMES) + r")\.weight$"


class ControlError(ModeldiffrError):
    pass


def expectation(kind: str, strength: float) -> str:
    if kind == "identity" or strength == 0 or (kind == "scale" and strength == 1):
        return "no_change"
    return "change"


def _seed(seed: int, name: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{name}".encode()).digest()[:8], "big") >> 1


def perturb(tensor, kind: str, strength: float, seed: int, name: str):
    import torch

    if kind == "identity":
        return tensor
    work = tensor.to(torch.float32)
    if kind == "noise":
        gen = torch.Generator().manual_seed(_seed(seed, name))
        std = float(work.std()) if work.numel() > 1 else 0.0
        noise = torch.randn(work.shape, generator=gen, dtype=torch.float32)
        work = work + noise * (strength * std)
    elif kind == "scale":
        work = work * strength
    elif kind == "zero":
        work = torch.zeros_like(work)
    elif kind == "prune":
        flat = work.abs().flatten()
        k = int(flat.numel() * strength)
        if k > 0:
            cutoff = flat.kthvalue(k).values
            work = torch.where(work.abs() <= cutoff, torch.zeros_like(work), work)
    else:
        raise ControlError(f"unknown control kind {kind!r}; choose one of {', '.join(KINDS)}")
    return work.to(tensor.dtype)


def make_control(
    base: str,
    out: str | Path,
    kind: str = "noise",
    strength: float = 0.05,
    match: str | None = None,
    seed: int = 0,
    revision: str | None = None,
    progress=lambda _: None,
) -> dict:
    if kind not in KINDS:
        raise ControlError(f"unknown control kind {kind!r}; choose one of {', '.join(KINDS)}")
    try:
        import torch
        from safetensors.torch import load_file, save_file
    except ImportError as exc:
        raise ControlError(
            'controls need torch and safetensors: pip install "modeldiffr[hf]"'
        ) from exc
    from modeldiffr.fingerprint import resolve_model_dir

    src, commit = resolve_model_dir(base, revision)
    shards = sorted(Path(src).glob("*.safetensors"))
    if not shards:
        raise ControlError(f"{base} has no safetensors files; controls need safetensors weights")
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise ControlError(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(match or DEFAULT_MATCH)
    changed = []
    for shard in shards:
        progress(f"{kind} {shard.name}")
        tensors = load_file(str(shard))
        for name in sorted(tensors):
            t = tensors[name]
            if not t.is_floating_point() or not pattern.search(name):
                continue
            new = perturb(t, kind, strength, seed, name)
            if not torch.equal(new, t):
                changed.append(name)
            tensors[name] = new.contiguous()
        save_file(tensors, str(out / shard.name), metadata={"format": "pt"})
    for f in sorted(Path(src).iterdir()):
        if f.is_file() and f.suffix in COPY_SUFFIXES and f.name != CONTROL_FILE:
            shutil.copyfile(f, out / f.name)
    if kind != "identity" and not changed and expectation(kind, strength) == "change":
        raise ControlError(f"the pattern {pattern.pattern!r} matched no floating point tensors")
    record = {
        "schema": SCHEMA,
        "base": base,
        "base_commit": commit,
        "kind": kind,
        "strength": strength,
        "match": pattern.pattern,
        "seed": seed,
        "expect": expectation(kind, strength),
        "tensors_changed": changed,
    }
    (out / CONTROL_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def read_control(model_dir: str | Path) -> dict | None:
    p = Path(model_dir) / CONTROL_FILE
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))
