from dataclasses import dataclass, field

from modeldiffr.interp.model import InterpError, capture_layers, unwrap


@dataclass
class Activations:
    layers: list[int]
    base: dict
    derivative: dict
    tokens: list[tuple[int, int]] = field(default_factory=list)
    ids: list[list[int]] = field(default_factory=list)
    texts_used: int = 0
    texts_skipped: int = 0

    @property
    def n(self) -> int:
        return len(self.tokens)


def tokenize_shared(base_tok, deriv_tok, texts: list[str], max_length: int):
    kept, skipped = [], 0
    for i, t in enumerate(texts):
        a = base_tok(t, add_special_tokens=True, truncation=True, max_length=max_length)[
            "input_ids"
        ]
        b = deriv_tok(t, add_special_tokens=True, truncation=True, max_length=max_length)[
            "input_ids"
        ]
        if a != b or len(a) < 2:
            skipped += 1
            continue
        kept.append((i, a))
    return kept, skipped


def _run(model, layers, batch, device, torch, pad):
    width = max(len(x) for x in batch)
    ids = torch.full((len(batch), width), pad, dtype=torch.long)
    mask = torch.zeros((len(batch), width), dtype=torch.long)
    for r, seq in enumerate(batch):
        ids[r, : len(seq)] = torch.tensor(seq)
        mask[r, : len(seq)] = 1
    with capture_layers(model, layers) as store, torch.no_grad():
        model(input_ids=ids.to(device), attention_mask=mask.to(device))
    return {i: store[i].float().cpu() for i in layers}


def capture(
    base,
    derivative,
    texts: list[str],
    layers: list[int],
    max_tokens: int = 50000,
    max_length: int = 256,
    batch_size: int = 8,
    skip_first: bool = True,
    progress=lambda _: None,
) -> Activations:
    import torch

    bm, bt = unwrap(base)
    dm, dt = unwrap(derivative)
    kept, skipped = tokenize_shared(bt, dt, texts, max_length)
    if not kept:
        raise InterpError("no text tokenizes the same way in both models; the vocabularies differ")
    pad = bt.pad_token_id if bt.pad_token_id is not None else 0
    out_b = {i: [] for i in layers}
    out_d = {i: [] for i in layers}
    tokens, ids = [], []
    total = 0
    start = 1 if skip_first else 0
    for b0 in range(0, len(kept), batch_size):
        chunk = kept[b0 : b0 + batch_size]
        seqs = [s for _, s in chunk]
        hb = _run(bm, layers, seqs, base.device, torch, pad)
        hd = _run(dm, layers, seqs, derivative.device, torch, pad)
        for r, (_, seq) in enumerate(chunk):
            n = len(seq) - start
            if n <= 0:
                continue
            take = min(n, max_tokens - total)
            if take <= 0:
                break
            for i in layers:
                out_b[i].append(hb[i][r, start : start + take])
                out_d[i].append(hd[i][r, start : start + take])
            ids.append(seq)
            doc = len(ids) - 1
            tokens += [(doc, start + p) for p in range(take)]
            total += take
        progress(f"captured {total} tokens from {min(b0 + batch_size, len(kept))} texts")
        if total >= max_tokens:
            break
    return Activations(
        layers=list(layers),
        base={i: torch.cat(out_b[i]) for i in layers},
        derivative={i: torch.cat(out_d[i]) for i in layers},
        tokens=tokens,
        ids=ids,
        texts_used=len(ids),
        texts_skipped=skipped,
    )


def last_token_activations(backend, texts: list[str], layers: list[int], batch_size: int = 8):
    import torch

    model, tok = unwrap(backend)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    rows = {i: [] for i in layers}
    for b0 in range(0, len(texts), batch_size):
        seqs = [tok(t, add_special_tokens=True)["input_ids"] for t in texts[b0 : b0 + batch_size]]
        h = _run(model, layers, seqs, backend.device, torch, pad)
        for r, seq in enumerate(seqs):
            for i in layers:
                rows[i].append(h[i][r, len(seq) - 1])
    return {i: torch.stack(rows[i]) for i in layers}
