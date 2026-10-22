from statistics import median

from modeldiffr.interp.model import unwrap


def render(tokenizer, text: str) -> list[int]:
    if getattr(tokenizer, "chat_template", None):
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True
        )
        return tokenizer(rendered, add_special_tokens=False)["input_ids"]
    return tokenizer(f"User: {text}\nAssistant:", add_special_tokens=True)["input_ids"]


def _greedy(model, device, ids, n, torch, eos):
    x = torch.tensor([ids], device=device)
    with torch.no_grad():
        out = model.generate(
            input_ids=x,
            attention_mask=torch.ones_like(x),
            max_new_tokens=n,
            do_sample=False,
            pad_token_id=eos,
        )
    return out[0, len(ids) :].tolist()


def _logprobs(model, device, ids, torch):
    x = torch.tensor([ids], device=device)
    with torch.no_grad():
        return torch.log_softmax(model(input_ids=x).logits[0].float(), dim=-1).cpu()


def probe_divergence(base, derivative, text: str, gen_tokens: int = 16) -> dict:
    import torch

    bm, tok = unwrap(base)
    dm, _ = unwrap(derivative)
    ids = render(tok, text)
    eos = tok.eos_token_id if tok.eos_token_id is not None else 0
    gen_d = _greedy(dm, derivative.device, ids, gen_tokens, torch, eos)
    gen_b = _greedy(bm, base.device, ids, gen_tokens, torch, eos)
    full = ids + gen_d
    lb = _logprobs(bm, base.device, full, torch)
    ld = _logprobs(dm, derivative.device, full, torch)
    start = len(ids) - 1
    span = slice(start, len(full) - 1) if len(gen_d) else slice(start, start + 1)
    kl = (ld[span].exp() * (ld[span] - lb[span])).sum(-1)
    first = float(kl[0])
    return {
        "kl_mean": float(kl.mean()),
        "kl_first": first,
        "derivative_output": tok.decode(gen_d, skip_special_tokens=True),
        "base_output": tok.decode(gen_b, skip_special_tokens=True),
        "same_output": gen_d == gen_b,
    }


def robust_z(values: list[float]) -> list[float]:
    m = median(values)
    mad = median(abs(v - m) for v in values)
    scale = 1.4826 * mad
    if scale <= 1e-12:
        spread = (max(values) - min(values)) or 1.0
        scale = spread * 1e-3
    return [(v - m) / scale for v in values]
