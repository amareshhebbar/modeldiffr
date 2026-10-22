import re
from contextlib import contextmanager

from modeldiffr.errors import ModeldiffrError

LAYER_PATHS = (
    "model.layers",
    "model.language_model.layers",
    "language_model.model.layers",
    "transformer.h",
    "gpt_neox.layers",
    "model.decoder.layers",
    "transformer.blocks",
)


class InterpError(ModeldiffrError):
    pass


def unwrap(backend):
    model = getattr(backend, "model", None)
    tok = getattr(backend, "tokenizer", None)
    if model is None or tok is None:
        raise InterpError(
            "representational and causal analysis needs the transformers backend (--backend hf)"
        )
    return model, tok


def find_layers(model):
    for path in LAYER_PATHS:
        obj = model
        for part in path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if obj is not None and hasattr(obj, "__len__") and len(obj) > 0:
            return obj
    raise InterpError(f"cannot find the decoder layers of {type(model).__name__}")


def n_layers(model) -> int:
    return len(find_layers(model))


def resolve_layers(model, spec) -> list[int]:
    total = n_layers(model)
    if spec in (None, "", "all"):
        return list(range(total))
    if spec == "middle":
        return [total // 2]
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)-(\d+)", part)
        if m:
            out += list(range(int(m.group(1)), int(m.group(2)) + 1))
        else:
            try:
                i = int(part)
            except ValueError as exc:
                raise InterpError(f"cannot read layer {part!r}; use 3, -1, 2-5 or middle") from exc
            out.append(i if i >= 0 else total + i)
    for i in out:
        if not 0 <= i < total:
            raise InterpError(f"layer {i} is out of range, the model has {total} layers")
    return sorted(set(out))


def _hidden(output):
    return output[0] if isinstance(output, tuple) else output


def _replace(output, hidden):
    if isinstance(output, tuple):
        return (hidden,) + tuple(output[1:])
    return hidden


@contextmanager
def capture_layers(model, layers: list[int]):
    store = {}
    handles = []
    blocks = find_layers(model)
    for i in layers:

        def hook(module, inputs, output, i=i):
            store[i] = _hidden(output).detach()

        handles.append(blocks[i].register_forward_hook(hook))
    try:
        yield store
    finally:
        for h in handles:
            h.remove()


@contextmanager
def edit_layer(model, layer: int, fn):
    block = find_layers(model)[layer]

    def hook(module, inputs, output):
        return _replace(output, fn(_hidden(output)))

    handle = block.register_forward_hook(hook)
    try:
        yield
    finally:
        handle.remove()
