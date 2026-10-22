BACKENDS = ("hf", "vllm", "llamacpp", "api")


def detect_backend(model: str, explicit: str | None = None) -> str:
    if explicit and explicit != "auto":
        return explicit
    if model.endswith(".gguf"):
        return "llamacpp"
    return "hf"


def make_backend(kind: str, model: str, **opts):
    if kind == "hf":
        from modeldiffr.backend import HFBackend

        return HFBackend(
            model,
            opts.get("device", "auto"),
            opts.get("revision"),
            opts.get("dtype", "auto"),
            opts.get("trust_remote_code", False),
        )
    if kind == "vllm":
        from modeldiffr.backends.vllm import VLLMBackend

        return VLLMBackend(
            model,
            revision=opts.get("revision"),
            dtype=opts.get("dtype", "auto"),
            trust_remote_code=opts.get("trust_remote_code", False),
            seed=opts.get("seed", 0),
        )
    if kind == "llamacpp":
        from modeldiffr.backends.llamacpp import LlamaCppBackend

        return LlamaCppBackend(
            model,
            n_ctx=opts.get("n_ctx", 4096),
            n_gpu_layers=opts.get("n_gpu_layers", 0),
            seed=opts.get("seed", 0),
            revision=opts.get("revision"),
        )
    if kind == "api":
        from modeldiffr.backends.api import APIBackend

        base = opts.get("api_base")
        if not base:
            raise ValueError(
                "the api backend needs --api-base, for example http://localhost:8000/v1"
            )
        return APIBackend(model, base, opts.get("api_key"), seed=opts.get("seed", 0))
    raise ValueError(f"unknown backend {kind!r}; choose one of {', '.join(BACKENDS)}")
