import math

from modeldiffr.proof.canonical import sha256_hex


def text_hash(text: str | None) -> str | None:
    return None if text is None else "sha256:" + sha256_hex(text.encode("utf-8"))


def logliks(backend, pairs: list[tuple[str, str]]) -> list[float]:
    if hasattr(backend, "choice_logprobs_batch"):
        return list(backend.choice_logprobs_batch(pairs))
    return [backend.choice_logprob(p, c) for p, c in pairs]


def truncate(text: str, stop: tuple[str, ...]) -> str:
    cut = len(text)
    for s in stop:
        i = text.find(s)
        if i != -1:
            cut = min(cut, i)
    return text[:cut]


def generate(
    backend, prompts: list[str], max_new_tokens: int, ctx, raw: bool = False, stop=()
) -> list[tuple[str, str | None]]:
    rendered: list[str | None]
    if raw:
        rendered = list(prompts)
        use_raw = True
    elif ctx.renderer is not None and hasattr(backend, "generate_raw"):
        rendered = [ctx.renderer.render_chat(p) for p in prompts]
        use_raw = True
    else:
        rendered = [
            backend.render_chat(p) if hasattr(backend, "render_chat") else None for p in prompts
        ]
        use_raw = False
    if use_raw:
        if hasattr(backend, "generate_raw_batch"):
            texts = list(backend.generate_raw_batch(rendered, max_new_tokens))
        else:
            texts = [backend.generate_raw(r, max_new_tokens) for r in rendered]
    elif hasattr(backend, "generate_batch"):
        texts = list(backend.generate_batch(prompts, max_new_tokens))
    else:
        texts = [backend.generate(p, max_new_tokens) for p in prompts]
    return [(truncate(t, stop), text_hash(r)) for t, r in zip(texts, rendered, strict=True)]


def softmax_confidence(scores: list[float], pick: int) -> float:
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    return exps[pick] / sum(exps)
