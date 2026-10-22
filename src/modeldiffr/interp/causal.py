import math
import random
from dataclasses import dataclass
from statistics import fmean

from modeldiffr.interp.model import InterpError, capture_layers, edit_layer, unwrap

SCHEMA = "modeldiffr.causal/1"
ID_PREFIX = "mdrc1:"


@dataclass
class MCItem:
    task: str
    id: str
    prompt: str
    continuations: list[str]
    answer: int


def mc_items(loaded) -> list[MCItem]:
    from modeldiffr.tasks.builtin import BuiltinCapability
    from modeldiffr.tasks.multiple_choice import MultipleChoiceTask

    out = []
    for task, items in loaded:
        for it in items:
            if isinstance(task, MultipleChoiceTask):
                out.append(
                    MCItem(
                        task.name, it.id, task.prompt(it), task.continuations(it), it.data["answer"]
                    )
                )
            elif isinstance(task, BuiltinCapability):
                out.append(
                    MCItem(
                        task.name,
                        it.id,
                        f"Question: {it.data['question']}\nAnswer:",
                        [" " + c for c in it.data["choices"]],
                        it.data["answer"],
                    )
                )
    return out


def _encode(tok, prompt, cont):
    p = tok(prompt, add_special_tokens=True)["input_ids"]
    full = tok(prompt + cont, add_special_tokens=True)["input_ids"]
    return full, min(len(p), len(full) - 1)


def _score(model, device, ids, start, torch):
    x = torch.tensor([ids], device=device)
    with torch.no_grad():
        logits = model(input_ids=x).logits.float()
    lp = torch.log_softmax(logits[0, :-1], dim=-1)
    picked = lp.gather(1, x[0, 1:].unsqueeze(1)).squeeze(1)
    return float(picked[start - 1 :].sum())


def _hidden(model, device, ids, layer, torch):
    with capture_layers(model, [layer]) as store, torch.no_grad():
        model(input_ids=torch.tensor([ids], device=device))
    return store[layer]


def _p_correct(scores, answer) -> float:
    m = max(scores)
    w = [math.exp(s - m) for s in scores]
    return w[answer] / sum(w)


class Patcher:
    def __init__(self, base, derivative, layer: int, crosscoder=None):
        import torch

        self.torch = torch
        self.bm, self.tok = unwrap(base)
        self.dm, dtok = unwrap(derivative)
        self.bdev, self.ddev = base.device, derivative.device
        self.layer = layer
        self.xc = crosscoder
        if self.xc is not None:
            dec = self.xc.decoders().detach()
            s = self.xc.scale
            self.unscaled = (dec[0] / s[0], dec[1] / s[1])

    def sequences(self, item: MCItem):
        return [_encode(self.tok, item.prompt, c) for c in item.continuations]

    def score(self, item: MCItem, condition: dict) -> float:
        torch = self.torch
        kind = condition["kind"]
        scores = []
        for ids, start in self.sequences(item):
            if kind == "base":
                scores.append(_score(self.bm, self.bdev, ids, start, torch))
                continue
            if kind == "derivative":
                scores.append(_score(self.dm, self.ddev, ids, start, torch))
                continue
            hb = _hidden(self.bm, self.bdev, ids, self.layer, torch)
            hd = _hidden(self.dm, self.ddev, ids, self.layer, torch)
            if kind == "patch_layer":
                fn = self._const(hd.to(hb.device, hb.dtype))
                model, dev = self.bm, self.bdev
            elif kind == "reverse_layer":
                fn = self._const(hb.to(hd.device, hd.dtype))
                model, dev = self.dm, self.ddev
            elif kind == "patch_features":
                fn = self._const(self._feature_patch(hb, hd, condition["features"]))
                model, dev = self.bm, self.bdev
            elif kind == "steer":
                v = condition["vector"].to(hb.device, hb.dtype) * condition["alpha"]
                fn = self._add(v)
                model, dev = self.bm, self.bdev
            else:
                raise InterpError(f"unknown condition {kind}")
            with edit_layer(model, self.layer, fn):
                scores.append(_score(model, dev, ids, start, torch))
        return _p_correct(scores, item.answer)

    def _const(self, value):
        return lambda h: value

    def _add(self, v):
        return lambda h: h + v

    def _feature_patch(self, hb, hd, features):
        torch = self.torch
        xb, xd = hb[0].float().cpu(), hd[0].float().cpu()
        with torch.no_grad():
            f = self.xc.encode(xb * self.xc.scale[0], xd * self.xc.scale[1])
            idx = torch.tensor(features, dtype=torch.long)
            delta = f[:, idx] @ (self.unscaled[1][idx] - self.unscaled[0][idx])
        return (hb + delta.unsqueeze(0).to(hb.device, hb.dtype)).to(hb.dtype)

    def attributions(self, items: list[MCItem]):
        torch = self.torch
        f_size = self.xc.b_enc.shape[0]
        total = torch.zeros(f_size)
        fired = torch.zeros(f_size)
        diff = (self.unscaled[1] - self.unscaled[0]).norm(dim=1)
        tokens = 0
        for item in items:
            ids, _ = _encode(self.tok, item.prompt, item.continuations[item.answer])
            hb = _hidden(self.bm, self.bdev, ids, self.layer, torch)[0].float().cpu()
            hd = _hidden(self.dm, self.ddev, ids, self.layer, torch)[0].float().cpu()
            with torch.no_grad():
                f = self.xc.encode(hb * self.xc.scale[0], hd * self.xc.scale[1])
            total += f.sum(0) * diff
            fired += (f > 0).float().sum(0)
            tokens += f.shape[0]
        return (total / max(1, tokens)).tolist(), (fired / max(1, tokens)).tolist()

    def mean_difference(self, items: list[MCItem]):
        torch = self.torch
        acc, n = None, 0
        for item in items:
            ids, _ = _encode(self.tok, item.prompt, item.continuations[item.answer])
            hb = _hidden(self.bm, self.bdev, ids, self.layer, torch)[0].float().cpu()
            hd = _hidden(self.dm, self.ddev, ids, self.layer, torch)[0].float().cpu()
            s = (hd - hb).sum(0)
            acc = s if acc is None else acc + s
            n += hb.shape[0]
        return acc / max(1, n)


def share_explained(base, deriv, cond, n_resamples=2000, seed=0, confidence=0.95) -> dict:
    n = len(base)
    delta = fmean(deriv) - fmean(base)
    moved = fmean(cond) - fmean(base)
    rng = random.Random(seed)
    deltas, shares = [], []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        d = fmean(deriv[i] - base[i] for i in idx)
        m = fmean(cond[i] - base[i] for i in idx)
        deltas.append(d)
        if d != 0:
            shares.append(m / d)
    deltas.sort()
    a = (1 - confidence) / 2
    lo_d, hi_d = deltas[int(a * (n_resamples - 1))], deltas[int((1 - a) * (n_resamples - 1))]
    out = {
        "items": n,
        "behavior_delta": delta,
        "behavior_ci": [lo_d, hi_d],
        "moved": moved,
        "share": moved / delta if delta else None,
        "share_ci": None,
        "explainable": lo_d > 0 or hi_d < 0,
    }
    if out["explainable"] and shares:
        shares.sort()
        k = len(shares)
        out["share_ci"] = [shares[int(a * (k - 1))], shares[int((1 - a) * (k - 1))]]
    return out
