def linear_cka(x, y) -> float:
    x = x - x.mean(0, keepdim=True)
    y = y - y.mean(0, keepdim=True)
    xy = (y.T @ x).pow(2).sum()
    xx = (x.T @ x).pow(2).sum().sqrt()
    yy = (y.T @ y).pow(2).sum().sqrt()
    denom = xx * yy
    return float(xy / denom) if float(denom) > 0 else 1.0


def compare_layer(b, d, max_rows: int = 20000, seed: int = 0) -> dict:
    import torch

    if b.shape[0] > max_rows:
        g = torch.Generator().manual_seed(seed)
        idx = torch.randperm(b.shape[0], generator=g)[:max_rows]
        b, d = b[idx], d[idx]
    b64, d64 = b.double(), d.double()
    nb = b64.norm(dim=1)
    diff = (d64 - b64).norm(dim=1)
    cos = torch.nn.functional.cosine_similarity(b64, d64, dim=1)
    mb, md = b64.mean(0), d64.mean(0)
    return {
        "cka": linear_cka(b64, d64),
        "cosine": float(cos.mean()),
        "relative_change": float((diff / nb.clamp_min(1e-12)).mean()),
        "mean_shift": float((md - mb).norm() / mb.norm().clamp_min(1e-12)),
        "norm_ratio": float(d64.norm(dim=1).mean() / nb.mean().clamp_min(1e-12)),
        "tokens": int(b.shape[0]),
    }


def compare_layers(acts) -> list[dict]:
    return [{"layer": i, **compare_layer(acts.base[i], acts.derivative[i])} for i in acts.layers]
