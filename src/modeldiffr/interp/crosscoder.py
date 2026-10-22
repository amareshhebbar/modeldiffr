import math
import time
from dataclasses import asdict, dataclass

from modeldiffr.interp.model import InterpError

CLASSES = ("shared", "shifted", "base_only", "derivative_only", "dead")


@dataclass
class CrosscoderConfig:
    dict_size: int = 4096
    k: int = 32
    variant: str = "standard"
    steps: int = 2000
    batch_size: int = 2048
    lr: float = 5e-4
    delta_penalty: float = 1e-3
    seed: int = 0
    holdout: float = 0.1

    def to_dict(self) -> dict:
        return asdict(self)


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise InterpError('crosscoders need torch: pip install "modeldiffr[hf]"') from exc
    return torch


def build(d_model: int, cfg: CrosscoderConfig):
    torch = _torch()
    nn = torch.nn

    class Crosscoder(nn.Module):
        def __init__(self):
            super().__init__()
            g = torch.Generator().manual_seed(cfg.seed)
            f = cfg.dict_size
            dec = torch.randn(2, f, d_model, generator=g)
            dec = dec / dec.norm(dim=-1, keepdim=True) * 0.1
            if cfg.variant == "delta":
                self.dec_shared = nn.Parameter(dec[0].clone())
                self.dec_delta = nn.Parameter(torch.zeros(f, d_model))
                enc = torch.stack([dec[0].T.clone(), dec[0].T.clone()])
            elif cfg.variant == "standard":
                self.dec = nn.Parameter(dec)
                enc = dec.transpose(1, 2).clone()
            else:
                raise InterpError(
                    f"unknown crosscoder variant {cfg.variant!r}; use standard or delta"
                )
            self.enc = nn.Parameter(enc)
            self.b_enc = nn.Parameter(torch.zeros(f))
            self.b_dec = nn.Parameter(torch.zeros(2, d_model))
            self.register_buffer("threshold", torch.tensor(0.0))
            self.register_buffer("scale", torch.ones(2))

        def decoders(self):
            if cfg.variant == "delta":
                return torch.stack([self.dec_shared, self.dec_shared + self.dec_delta])
            return self.dec

        def pre(self, xb, xd):
            return torch.relu(xb @ self.enc[0] + xd @ self.enc[1] + self.b_enc)

        def encode(self, xb, xd, train=False):
            h = self.pre(xb, xd)
            if train:
                k = min(cfg.k * h.shape[0], h.numel())
                vals, idx = h.flatten().topk(k)
                out = torch.zeros_like(h).flatten().scatter(0, idx, vals).view_as(h)
                kept = vals[vals > 0]
                return out, (kept.min() if kept.numel() else None)
            return torch.where(h > self.threshold, h, torch.zeros_like(h))

        def decode(self, f):
            dec = self.decoders()
            return f @ dec[0] + self.b_dec[0], f @ dec[1] + self.b_dec[1]

    return Crosscoder()


def _fve(x, xh) -> float:
    resid = (x - xh).pow(2).sum()
    total = (x - x.mean(0, keepdim=True)).pow(2).sum()
    return float(1 - resid / total) if float(total) > 0 else 1.0


def train(xb, xd, cfg: CrosscoderConfig, progress=lambda _: None):
    torch = _torch()
    if xb.shape != xd.shape:
        raise InterpError("base and derivative activations must have the same shape")
    torch.manual_seed(cfg.seed)
    n, d = xb.shape
    g = torch.Generator().manual_seed(cfg.seed)
    perm = torch.randperm(n, generator=g)
    n_hold = max(1, int(n * cfg.holdout)) if n > 10 else 0
    hold, fit = perm[:n_hold], perm[n_hold:]
    scale = torch.tensor(
        [
            math.sqrt(d) / float(xb[fit].norm(dim=1).mean().clamp_min(1e-12)),
            math.sqrt(d) / float(xd[fit].norm(dim=1).mean().clamp_min(1e-12)),
        ]
    )
    model = build(d, cfg)
    model.scale.copy_(scale)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, betas=(0.9, 0.999))
    decay_from = int(cfg.steps * 0.8)
    thresholds = []
    started = time.monotonic()
    last = None
    fired = torch.zeros(cfg.dict_size, dtype=torch.bool)
    for step in range(cfg.steps):
        if step >= decay_from:
            for group in opt.param_groups:
                group["lr"] = cfg.lr * (cfg.steps - step) / max(1, cfg.steps - decay_from)
        idx = fit[torch.randint(len(fit), (min(cfg.batch_size, len(fit)),), generator=g)]
        b, dd = xb[idx] * scale[0], xd[idx] * scale[1]
        f, tmin = model.encode(b, dd, train=True)
        rb, rd = model.decode(f)
        loss = ((b - rb).pow(2).sum(-1) + (dd - rd).pow(2).sum(-1)).mean()
        if cfg.variant == "delta":
            loss = loss + cfg.delta_penalty * model.dec_delta.norm(dim=1).sum()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        fired |= (f > 0).any(0)
        if tmin is not None and step >= cfg.steps // 2:
            thresholds.append(float(tmin.detach()))
        last = float(loss.detach())
        if step % max(1, cfg.steps // 10) == 0 or step == cfg.steps - 1:
            progress(f"step {step + 1}/{cfg.steps} loss {last:.4f}")
    model.threshold.fill_(sum(thresholds) / len(thresholds) if thresholds else 0.0)
    model.eval()
    stats = {
        "final_loss": last,
        "seconds": round(time.monotonic() - started, 1),
        "threshold": float(model.threshold),
        "tokens_fit": int(len(fit)),
        "tokens_holdout": int(n_hold),
        "dead_in_training": int((~fired).sum()),
    }
    if n_hold:
        with torch.no_grad():
            b, dd = xb[hold] * scale[0], xd[hold] * scale[1]
            f = model.encode(b, dd)
            rb, rd = model.decode(f)
            stats["fve_base"] = _fve(b, rb)
            stats["fve_derivative"] = _fve(dd, rd)
            stats["l0"] = float((f > 0).float().sum(1).mean())
    return model, stats


def feature_activations(model, xb, xd, chunk: int = 4096):
    torch = _torch()
    with torch.no_grad():
        for start in range(0, xb.shape[0], chunk):
            b = xb[start : start + chunk] * model.scale[0]
            d = xd[start : start + chunk] * model.scale[1]
            yield start, model.encode(b, d)


def classify(
    model, density, base_only: float = 0.15, derivative_only: float = 0.85, shift: float = 0.5
):
    torch = _torch()
    with torch.no_grad():
        dec = model.decoders()
        nb, nd = dec[0].norm(dim=1), dec[1].norm(dim=1)
        rel = nd / (nb + nd).clamp_min(1e-12)
        cos = torch.nn.functional.cosine_similarity(dec[0], dec[1], dim=1)
    labels = []
    for i in range(rel.shape[0]):
        if density[i] == 0:
            labels.append("dead")
        elif rel[i] < base_only:
            labels.append("base_only")
        elif rel[i] > derivative_only:
            labels.append("derivative_only")
        elif cos[i] < shift:
            labels.append("shifted")
        else:
            labels.append("shared")
    return labels, rel.tolist(), cos.tolist()


def save(model, path, cfg: CrosscoderConfig) -> str:
    import hashlib
    import json

    from safetensors.torch import save_file

    tensors = {k: v.detach().contiguous().cpu() for k, v in model.state_dict().items()}
    save_file(tensors, str(path), metadata={"modeldiffr": json.dumps(cfg.to_dict())})
    return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()


def load(path, d_model: int | None = None):
    import json

    from safetensors import safe_open
    from safetensors.torch import load_file

    with safe_open(str(path), framework="pt") as f:
        cfg = CrosscoderConfig(**json.loads(f.metadata()["modeldiffr"]))
    tensors = load_file(str(path))
    d = d_model or tensors["b_dec"].shape[1]
    model = build(d, cfg)
    model.load_state_dict(tensors)
    model.eval()
    return model, cfg
