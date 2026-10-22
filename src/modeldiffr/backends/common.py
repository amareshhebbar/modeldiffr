import hashlib


def vocab_signature_from_tokens(tokens: dict[str, int]) -> str:
    payload = "\n".join(f"{k}\t{v}" for k, v in sorted(tokens.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render_template(template: str, prompt: str, bos: str = "", eos: str = "") -> str:
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)

    def raise_exception(message):
        raise ValueError(message)

    env.globals["raise_exception"] = raise_exception
    return env.from_string(template).render(
        messages=[{"role": "user", "content": prompt}],
        add_generation_prompt=True,
        bos_token=bos,
        eos_token=eos,
    )
