import hashlib
from typing import Protocol


class Backend(Protocol):
    name: str

    def metadata(self) -> dict: ...

    def choice_logprob(self, prompt: str, continuation: str) -> float: ...

    def generate(self, prompt: str, max_new_tokens: int) -> str: ...

    def vocab_signature(self) -> str: ...

    def divergence_to(self, other: "Backend", text: str) -> float: ...


class FingerprintingBackend(Backend, Protocol):
    def fingerprint(self, weights: bool = True) -> dict: ...

    def render_chat(self, prompt: str) -> str: ...

    def generate_raw(self, text: str, max_new_tokens: int) -> str: ...


class MissingDependencyError(RuntimeError):
    pass


def _require_hf():
    try:
        import torch
        import transformers
    except ImportError as exc:
        raise MissingDependencyError(
            'Hugging Face support is not installed. Run: pip install "modeldiffr[hf]"'
        ) from exc
    return torch, transformers


def resolve_device(device: str) -> str:
    torch, _ = _require_hf()
    if device != "auto":
        return device
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class HFBackend:
    def __init__(
        self,
        model_id: str,
        device: str = "auto",
        revision: str | None = None,
        dtype: str = "auto",
        trust_remote_code: bool = False,
    ):
        torch, transformers = _require_hf()
        self._torch = torch
        self.name = model_id
        self.device = resolve_device(device)
        self.revision = revision
        torch_dtype = {
            "auto": "auto",
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }[dtype]
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            model_id, revision=revision, trust_remote_code=trust_remote_code
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = transformers.AutoModelForCausalLM.from_pretrained(
            model_id,
            revision=revision,
            torch_dtype=torch_dtype,
            trust_remote_code=trust_remote_code,
        ).to(self.device)
        self.model.eval()

    def commit(self) -> str | None:
        return getattr(self.model.config, "_commit_hash", None)

    def source_dir(self):
        from pathlib import Path

        local = Path(self.name)
        if local.is_dir():
            return local
        from huggingface_hub import snapshot_download

        patterns = ["*.safetensors", "*.json", "*.model", "*.txt", "*.jinja", "*.bin"]
        rev = self.commit() or self.revision
        try:
            return Path(
                snapshot_download(
                    self.name, revision=rev, allow_patterns=patterns, local_files_only=True
                )
            )
        except Exception:
            return Path(snapshot_download(self.name, revision=rev, allow_patterns=patterns))

    def fingerprint(self, weights: bool = True) -> dict:
        from modeldiffr.fingerprint import tokenizer_fingerprint, weights_fingerprint

        directory = self.source_dir()
        out = {
            "commit": self.commit(),
            "tokenizer": tokenizer_fingerprint(self.tokenizer, directory),
        }
        out["weights"] = weights_fingerprint(directory).to_dict() if weights else None
        return out

    def metadata(self) -> dict:
        config = self.model.config
        return {
            "model_id": self.name,
            "revision": self.revision or getattr(config, "_commit_hash", None),
            "architecture": (getattr(config, "architectures", None) or [None])[0],
            "parameters": sum(p.numel() for p in self.model.parameters()),
            "dtype": str(next(self.model.parameters()).dtype),
            "device": self.device,
            "has_chat_template": bool(getattr(self.tokenizer, "chat_template", None)),
        }

    def vocab_signature(self) -> str:
        vocab = self.tokenizer.get_vocab()
        payload = "\n".join(f"{k}\t{v}" for k, v in sorted(vocab.items()))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def max_context(self) -> int | None:
        return getattr(self.model.config, "max_position_embeddings", None)

    def choice_logprobs_batch(
        self, pairs: list[tuple[str, str]], batch_size: int = 16
    ) -> list[float]:
        torch = self._torch
        encoded = []
        for prompt, continuation in pairs:
            p = self.tokenizer(prompt, add_special_tokens=True)["input_ids"]
            full = self.tokenizer(prompt + continuation, add_special_tokens=True)["input_ids"]
            start = min(len(p), len(full) - 1)
            encoded.append((full, start))
        order = sorted(range(len(encoded)), key=lambda i: len(encoded[i][0]))
        out = [0.0] * len(encoded)
        pad = self.tokenizer.pad_token_id or 0
        for b in range(0, len(order), batch_size):
            idx = order[b : b + batch_size]
            width = max(len(encoded[i][0]) for i in idx)
            ids = torch.full((len(idx), width), pad, dtype=torch.long)
            mask = torch.zeros((len(idx), width), dtype=torch.long)
            for row, i in enumerate(idx):
                seq = encoded[i][0]
                ids[row, : len(seq)] = torch.tensor(seq)
                mask[row, : len(seq)] = 1
            ids, mask = ids.to(self.device), mask.to(self.device)
            with torch.no_grad():
                logits = self.model(input_ids=ids, attention_mask=mask).logits.float()
            logprobs = torch.log_softmax(logits[:, :-1], dim=-1)
            picked = logprobs.gather(2, ids[:, 1:].unsqueeze(-1)).squeeze(-1)
            for row, i in enumerate(idx):
                seq, start = encoded[i]
                out[i] = float(picked[row, start - 1 : len(seq) - 1].sum())
        return out

    def generate_raw_batch(
        self, texts: list[str], max_new_tokens: int, batch_size: int = 8
    ) -> list[str]:
        torch = self._torch
        out = [""] * len(texts)
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        side = self.tokenizer.padding_side
        self.tokenizer.padding_side = "left"
        try:
            for b in range(0, len(order), batch_size):
                idx = order[b : b + batch_size]
                enc = self.tokenizer(
                    [texts[i] for i in idx],
                    return_tensors="pt",
                    padding=True,
                    add_special_tokens=False,
                ).to(self.device)
                with torch.no_grad():
                    gen = self.model.generate(
                        **enc,
                        max_new_tokens=max_new_tokens,
                        do_sample=False,
                        pad_token_id=self.tokenizer.pad_token_id,
                    )
                new = gen[:, enc["input_ids"].shape[1] :]
                for row, i in enumerate(idx):
                    out[i] = self.tokenizer.decode(new[row], skip_special_tokens=True)
        finally:
            self.tokenizer.padding_side = side
        return out

    def token_logprobs(self, text: str):
        inputs = self._encode(text)
        ids = inputs["input_ids"][0].tolist()
        return ids, self._logprobs(text).cpu().numpy()

    def _encode(self, text: str):
        return self.tokenizer(text, return_tensors="pt", add_special_tokens=True).to(self.device)

    def choice_logprob(self, prompt: str, continuation: str) -> float:
        torch = self._torch
        prompt_ids = self.tokenizer(prompt, add_special_tokens=True)["input_ids"]
        full_ids = self.tokenizer(prompt + continuation, add_special_tokens=True)["input_ids"]
        start = len(prompt_ids)
        if start >= len(full_ids):
            start = len(full_ids) - 1
        ids = torch.tensor([full_ids], device=self.device)
        with torch.no_grad():
            logits = self.model(ids).logits.float()
        logprobs = torch.log_softmax(logits[0, :-1], dim=-1)
        targets = ids[0, 1:]
        picked = logprobs.gather(1, targets.unsqueeze(1)).squeeze(1)
        return float(picked[start - 1 :].sum())

    def render_chat(self, prompt: str) -> str:
        return self._chat_prompt(prompt)

    def _chat_prompt(self, prompt: str) -> str:
        if getattr(self.tokenizer, "chat_template", None):
            return self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
        return f"User: {prompt}\nAssistant:"

    def generate(self, prompt: str, max_new_tokens: int) -> str:
        return self.generate_raw(self._chat_prompt(prompt), max_new_tokens)

    def generate_raw(self, text: str, max_new_tokens: int) -> str:
        torch = self._torch
        inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).to(self.device)
        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        new_tokens = output[0, inputs["input_ids"].shape[1] :]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _logprobs(self, text: str):
        torch = self._torch
        inputs = self._encode(text)
        with torch.no_grad():
            logits = self.model(**inputs).logits.float()
        return torch.log_softmax(logits[0], dim=-1)

    def divergence_to(self, other: "HFBackend", text: str) -> float:
        torch = self._torch
        p = self._logprobs(text)
        q = other._logprobs(text).to(p.device)
        vocab = min(p.shape[-1], q.shape[-1])
        p, q = p[:, :vocab], q[:, :vocab]
        kl = (p.exp() * (p - q)).sum(dim=-1)
        return float(torch.clamp(kl, min=0.0).mean())
