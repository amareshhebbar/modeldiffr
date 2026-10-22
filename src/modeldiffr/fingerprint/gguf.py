import hashlib
import struct
from pathlib import Path

from modeldiffr.fingerprint.weights import (
    ALGORITHM,
    UnsupportedWeightsError,
    WeightsFingerprint,
    root_from_leaves,
    tensor_leaf,
)

GGML_TYPES = {
    0: ("F32", 1, 4),
    1: ("F16", 1, 2),
    2: ("Q4_0", 32, 18),
    3: ("Q4_1", 32, 20),
    6: ("Q5_0", 32, 22),
    7: ("Q5_1", 32, 24),
    8: ("Q8_0", 32, 34),
    9: ("Q8_1", 32, 40),
    10: ("Q2_K", 256, 84),
    11: ("Q3_K", 256, 110),
    12: ("Q4_K", 256, 144),
    13: ("Q5_K", 256, 176),
    14: ("Q6_K", 256, 210),
    15: ("Q8_K", 256, 292),
    16: ("IQ2_XXS", 256, 66),
    17: ("IQ2_XS", 256, 74),
    18: ("IQ3_XXS", 256, 98),
    19: ("IQ1_S", 256, 50),
    20: ("IQ4_NL", 32, 18),
    21: ("IQ3_S", 256, 110),
    22: ("IQ2_S", 256, 82),
    23: ("IQ4_XS", 256, 136),
    24: ("I8", 1, 1),
    25: ("I16", 1, 2),
    26: ("I32", 1, 4),
    27: ("I64", 1, 8),
    28: ("F64", 1, 8),
    29: ("IQ1_M", 256, 56),
    30: ("BF16", 1, 2),
    34: ("TQ1_0", 256, 54),
    35: ("TQ2_0", 256, 66),
    39: ("MXFP4", 32, 17),
    40: ("NVFP4", 64, 36),
    41: ("Q1_0", 128, 18),
}

_SCALARS = {
    0: "<B",
    1: "<b",
    2: "<H",
    3: "<h",
    4: "<I",
    5: "<i",
    6: "<f",
    7: "<?",
    10: "<Q",
    11: "<q",
    12: "<d",
}


class _Reader:
    def __init__(self, f):
        self.f = f

    def take(self, fmt: str):
        size = struct.calcsize(fmt)
        data = self.f.read(size)
        if len(data) != size:
            raise UnsupportedWeightsError("truncated GGUF file")
        return struct.unpack(fmt, data)[0]

    def string(self) -> str:
        n = self.take("<Q")
        if n > 1 << 30:
            raise UnsupportedWeightsError("GGUF string too long")
        return self.f.read(n).decode("utf-8", "replace")

    def value(self, vtype: int):
        if vtype in _SCALARS:
            return self.take(_SCALARS[vtype])
        if vtype == 8:
            return self.string()
        if vtype == 9:
            itype = self.take("<I")
            count = self.take("<Q")
            return [self.value(itype) for _ in range(count)]
        raise UnsupportedWeightsError(f"unknown GGUF value type {vtype}")


def read_gguf(path: str | Path) -> dict:
    path = Path(path)
    with path.open("rb") as f:
        if f.read(4) != b"GGUF":
            raise UnsupportedWeightsError(f"{path.name} is not a GGUF file")
        r = _Reader(f)
        version = r.take("<I")
        if version < 2:
            raise UnsupportedWeightsError(f"GGUF version {version} is not supported")
        n_tensors = r.take("<Q")
        n_kv = r.take("<Q")
        meta = {}
        for _ in range(n_kv):
            key = r.string()
            meta[key] = r.value(r.take("<I"))
        tensors = []
        for _ in range(n_tensors):
            name = r.string()
            n_dims = r.take("<I")
            dims = [r.take("<Q") for _ in range(n_dims)]
            ttype = r.take("<I")
            offset = r.take("<Q")
            tensors.append({"name": name, "shape": dims, "type": ttype, "offset": offset})
        align = int(meta.get("general.alignment", 32))
        pos = f.tell()
        data_start = pos + (-pos % align)
    return {"version": version, "metadata": meta, "tensors": tensors, "data_start": data_start}


def tensor_nbytes(shape: list[int], ttype: int) -> int:
    if ttype not in GGML_TYPES:
        raise UnsupportedWeightsError(f"unknown GGML tensor type {ttype}")
    _, block, size = GGML_TYPES[ttype]
    n = 1
    for d in shape:
        n *= d
    if n % block:
        raise UnsupportedWeightsError("tensor size is not a multiple of its block size")
    return n // block * size


def gguf_fingerprint(path: str | Path) -> WeightsFingerprint:
    info = read_gguf(path)
    leaves: dict[str, str] = {}
    total = 0
    with Path(path).open("rb") as f:
        for t in info["tensors"]:
            nbytes = tensor_nbytes(t["shape"], t["type"])
            f.seek(info["data_start"] + t["offset"])
            h = hashlib.sha256()
            remaining = nbytes
            while remaining:
                chunk = f.read(min(8 << 20, remaining))
                if not chunk:
                    raise UnsupportedWeightsError(f"truncated tensor {t['name']}")
                h.update(chunk)
                remaining -= len(chunk)
            leaves[t["name"]] = tensor_leaf(
                t["name"], GGML_TYPES[t["type"]][0], t["shape"], h.hexdigest()
            )
            total += nbytes
    return WeightsFingerprint(
        root=root_from_leaves(leaves),
        tensors=len(leaves),
        bytes=total,
        format="gguf",
        leaves=leaves,
        algorithm=ALGORITHM,
    )


def gguf_vocab(path: str | Path) -> dict:
    meta = read_gguf(path)["metadata"]
    tokens = meta.get("tokenizer.ggml.tokens") or []
    return {
        "tokens": tokens,
        "chat_template": meta.get("tokenizer.chat_template"),
        "bos_id": meta.get("tokenizer.ggml.bos_token_id"),
        "eos_id": meta.get("tokenizer.ggml.eos_token_id"),
        "context_length": next((v for k, v in meta.items() if k.endswith(".context_length")), None),
        "architecture": meta.get("general.architecture"),
        "name": meta.get("general.name"),
    }
