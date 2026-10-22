import math
from pathlib import Path

from modeldiffr.backend import MissingDependencyError
from modeldiffr.backends.common import render_template, vocab_signature_from_tokens


def _log_softmax(row):
    m = max(row)
    s = sum(math.exp(x - m) for x in row)
    lse = m + math.log(s)
    return [x - lse for x in row]


class LlamaCppBackend:
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        seed: int = 0,
        revision=None,
    ):
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise MissingDependencyError(
                'llama.cpp support is not installed. Run: pip install "modeldiffr[llamacpp]"'
            ) from exc
        path = Path(model_path)
        if not path.exists() and ":" in model_path:
            from huggingface_hub import hf_hub_download

            repo, _, filename = model_path.partition(":")
            path = Path(hf_hub_download(repo, filename, revision=revision))
        self.path = path
        self.name = model_path
        self.n_ctx = n_ctx
        self.llm = Llama(
            model_path=str(path),
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            logits_all=True,
            seed=seed,
            verbose=False,
        )
        from modeldiffr.fingerprint.gguf import gguf_vocab

        self._vocab = gguf_vocab(path)
        self._tokens = self._vocab["tokens"]

    def max_context(self) -> int:
        return self.n_ctx

    def metadata(self) -> dict:
        return {
            "model_id": self.name,
            "revision": None,
            "backend": "llamacpp",
            "architecture": self._vocab.get("architecture"),
            "device": "cpu" if not getattr(self.llm, "n_gpu_layers", 0) else "gpu",
            "dtype": "gguf",
            "has_chat_template": bool(self._vocab.get("chat_template")),
        }

    def fingerprint(self, weights: bool = True) -> dict:
        from modeldiffr.fingerprint.gguf import gguf_fingerprint
        from modeldiffr.fingerprint.tokenizer import ALGORITHM, _h, template_hash

        tokens = {t: i for i, t in enumerate(self._tokens)}
        special = {
            "bos_token": self._tokens[self._vocab["bos_id"]]
            if self._vocab.get("bos_id") is not None
            else None,
            "eos_token": self._tokens[self._vocab["eos_id"]]
            if self._vocab.get("eos_id") is not None
            else None,
            "pad_token": None,
            "unk_token": None,
        }
        tok = {
            "algorithm": ALGORITHM,
            "vocab": _h(
                {
                    "vocab": [
                        [t, i] for t, i in sorted(tokens.items(), key=lambda kv: (kv[1], kv[0]))
                    ],
                    "added": [],
                }
            ),
            "vocab_size": len(tokens),
            "special_tokens": special,
            "chat_template": template_hash(self._vocab.get("chat_template")),
            "tokenizer_json": None,
        }
        return {
            "commit": None,
            "tokenizer": tok,
            "weights": gguf_fingerprint(self.path).to_dict() if weights else None,
        }

    def vocab_signature(self) -> str:
        return vocab_signature_from_tokens({t: i for i, t in enumerate(self._tokens)})

    def _tokenize(self, text: str) -> list[int]:
        return self.llm.tokenize(text.encode("utf-8"), add_bos=True, special=True)

    def token_logprobs(self, text: str):
        import numpy as np

        ids = self._tokenize(text)
        self.llm.reset()
        self.llm.eval(ids)
        scores = np.array(self.llm.scores[: len(ids)], dtype=np.float32)
        scores = scores - scores.max(axis=-1, keepdims=True)
        return ids, scores - np.log(np.exp(scores).sum(axis=-1, keepdims=True))

    def choice_logprob(self, prompt: str, continuation: str) -> float:
        p = self._tokenize(prompt)
        full = self._tokenize(prompt + continuation)
        start = min(len(p), len(full) - 1)
        ids, lp = self.token_logprobs(prompt + continuation)
        return float(sum(lp[pos - 1][full[pos]] for pos in range(max(start, 1), len(full))))

    def render_chat(self, prompt: str) -> str:
        template = self._vocab.get("chat_template")
        if not template:
            return f"User: {prompt}\nAssistant:"
        bos = self._tokens[self._vocab["bos_id"]] if self._vocab.get("bos_id") is not None else ""
        eos = self._tokens[self._vocab["eos_id"]] if self._vocab.get("eos_id") is not None else ""
        return render_template(template, prompt, bos, eos)

    def generate_raw(self, text: str, max_new_tokens: int) -> str:
        self.llm.reset()
        out = self.llm.create_completion(
            text, max_tokens=max_new_tokens, temperature=0.0, top_k=1, seed=0
        )
        return out["choices"][0]["text"]

    def generate(self, prompt: str, max_new_tokens: int) -> str:
        return self.generate_raw(self.render_chat(prompt), max_new_tokens)

    def divergence_to(self, other, text: str) -> float:
        from modeldiffr.tasks.divergence import generic_kl

        value = generic_kl(self, other, text)
        if value is None:
            raise ValueError("the two models tokenize this text differently")
        return value


__all__ = ["LlamaCppBackend", "_log_softmax"]
