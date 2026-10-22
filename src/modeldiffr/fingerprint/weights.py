import hashlib
import json
import struct
from dataclasses import dataclass, field
from pathlib import Path

from modeldiffr.proof.canonical import canonical_json
from modeldiffr.proof.merkle import leaf_hash, merkle_root

ALGORITHM = "modeldiffr.weights/1"
CHUNK = 8 << 20

_TORCH_DTYPES = {
    "float64": "F64",
    "float32": "F32",
    "float16": "F16",
    "bfloat16": "BF16",
    "float8_e4m3fn": "F8_E4M3",
    "float8_e5m2": "F8_E5M2",
    "int64": "I64",
    "int32": "I32",
    "int16": "I16",
    "int8": "I8",
    "uint8": "U8",
    "bool": "BOOL",
}


class UnsupportedWeightsError(RuntimeError):
    pass


@dataclass
class WeightsFingerprint:
    root: str
    tensors: int
    bytes: int
    format: str
    leaves: dict[str, str] = field(default_factory=dict)
    algorithm: str = ALGORITHM

    def to_dict(self, include_leaves: bool = True) -> dict:
        out = {
            "algorithm": self.algorithm,
            "root": self.root,
            "tensors": self.tensors,
            "bytes": self.bytes,
            "format": self.format,
        }
        if include_leaves:
            out["leaves"] = dict(self.leaves)
        return out


def tensor_leaf(name: str, dtype: str, shape: list[int], data_sha256: str) -> str:
    record = {"name": name, "dtype": dtype, "shape": list(shape), "data": data_sha256}
    return leaf_hash(canonical_json(record)).hex()


def root_from_leaves(leaves: dict[str, str]) -> str:
    ordered = [bytes.fromhex(leaves[k]) for k in sorted(leaves)]
    return "sha256:" + merkle_root(ordered).hex()


def _safetensors_entries(path: Path):
    with path.open("rb") as f:
        (header_len,) = struct.unpack("<Q", f.read(8))
        if header_len > 100 << 20:
            raise UnsupportedWeightsError(f"{path.name}: header too large to be safetensors")
        header = json.loads(f.read(header_len))
        base = 8 + header_len
        for name, meta in header.items():
            if name == "__metadata__":
                continue
            start, end = meta["data_offsets"]
            f.seek(base + start)
            h = hashlib.sha256()
            remaining = end - start
            while remaining:
                chunk = f.read(min(CHUNK, remaining))
                if not chunk:
                    raise UnsupportedWeightsError(f"{path.name}: truncated tensor {name}")
                h.update(chunk)
                remaining -= len(chunk)
            yield name, meta["dtype"], meta["shape"], h.hexdigest(), end - start


def _torch_entries(path: Path):
    try:
        import torch
    except ImportError as exc:
        raise UnsupportedWeightsError(
            f"{path.name} is a PyTorch pickle; install torch or convert the model to safetensors"
        ) from exc
    state = torch.load(str(path), map_location="cpu", weights_only=True, mmap=True)
    if not isinstance(state, dict):
        raise UnsupportedWeightsError(f"{path.name}: expected a state dict")
    for name, tensor in state.items():
        if not hasattr(tensor, "dtype"):
            continue
        dtype = _TORCH_DTYPES.get(str(tensor.dtype).removeprefix("torch."))
        if dtype is None:
            raise UnsupportedWeightsError(
                f"{path.name}: unsupported dtype {tensor.dtype} in {name}"
            )
        data = tensor.detach().contiguous().view(torch.uint8).numpy().tobytes()
        yield name, dtype, list(tensor.shape), hashlib.sha256(data).hexdigest(), len(data)


def weight_files(model_dir: Path) -> tuple[str, list[Path]]:
    st = sorted(model_dir.glob("*.safetensors"))
    if st:
        return "safetensors", st
    pt = sorted(p for p in model_dir.glob("*.bin") if "training_args" not in p.name)
    pt += sorted(model_dir.glob("*.pt")) + sorted(model_dir.glob("*.pth"))
    if pt:
        return "pytorch", pt
    if any(model_dir.glob("*.gguf")):
        return "gguf", sorted(model_dir.glob("*.gguf"))
    raise UnsupportedWeightsError(f"no weight files found in {model_dir}")


def weights_fingerprint(model_dir: str | Path) -> WeightsFingerprint:
    model_dir = Path(model_dir)
    if model_dir.is_file() and model_dir.suffix == ".gguf":
        from modeldiffr.fingerprint.gguf import gguf_fingerprint

        return gguf_fingerprint(model_dir)
    fmt, files = weight_files(model_dir)
    if fmt == "gguf":
        if len(files) != 1:
            raise UnsupportedWeightsError("pass the path of one .gguf file, the folder has several")
        from modeldiffr.fingerprint.gguf import gguf_fingerprint

        return gguf_fingerprint(files[0])
    reader = _safetensors_entries if fmt == "safetensors" else _torch_entries
    leaves: dict[str, str] = {}
    total = 0
    for path in files:
        for name, dtype, shape, digest, size in reader(path):
            if name in leaves:
                raise UnsupportedWeightsError(f"tensor {name} appears in more than one file")
            leaves[name] = tensor_leaf(name, dtype, shape, digest)
            total += size
    return WeightsFingerprint(
        root=root_from_leaves(leaves), tensors=len(leaves), bytes=total, format=fmt, leaves=leaves
    )


def diff_weights(base: dict[str, str], derivative: dict[str, str], limit: int = 200) -> dict:
    changed = sorted(k for k in base.keys() & derivative.keys() if base[k] != derivative[k])
    added = sorted(derivative.keys() - base.keys())
    removed = sorted(base.keys() - derivative.keys())
    shared = len(base.keys() & derivative.keys())
    return {
        "identical": not changed and not added and not removed,
        "shared": shared,
        "changed_count": len(changed),
        "added_count": len(added),
        "removed_count": len(removed),
        "unchanged_count": shared - len(changed),
        "changed": changed[:limit],
        "added": added[:limit],
        "removed": removed[:limit],
        "truncated": max(len(changed), len(added), len(removed)) > limit,
    }


def resolve_model_dir(model: str, revision: str | None = None) -> tuple[Path, str | None]:
    local = Path(model)
    if local.is_dir():
        return local, None
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise UnsupportedWeightsError(
            'downloading from the Hub needs huggingface_hub: pip install "modeldiffr[hf]"'
        ) from exc
    patterns = [
        "*.safetensors",
        "*.json",
        "*.model",
        "*.txt",
        "*.jinja",
        "*.bin",
        "*.pt",
        "*.pth",
        "model.sig",
    ]
    path = Path(snapshot_download(model, revision=revision, allow_patterns=patterns))
    commit = path.name if len(path.name) == 40 else None
    return path, commit
