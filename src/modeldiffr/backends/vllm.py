from modeldiffr.backend import MissingDependencyError
from modeldiffr.backends.common import vocab_signature_from_tokens


class VLLMBackend:
    supports_divergence = False

    def __init__(
        self,
        model_id: str,
        revision: str | None = None,
        dtype: str = "auto",
        trust_remote_code: bool = False,
        gpu_memory_utilization: float = 0.85,
        max_model_len: int | None = None,
        seed: int = 0,
    ):
        try:
            from vllm import LLM, SamplingParams
        except ImportError as exc:
            raise MissingDependencyError(
                'vLLM is not installed. Run: pip install "modeldiffr[vllm]"'
            ) from exc
        self._SamplingParams = SamplingParams
        self.name = model_id
        self.revision = revision
        kwargs = {
            "model": model_id,
            "revision": revision,
            "dtype": dtype,
            "trust_remote_code": trust_remote_code,
            "gpu_memory_utilization": gpu_memory_utilization,
            "seed": seed,
        }
        if max_model_len:
            kwargs["max_model_len"] = max_model_len
        self.llm = LLM(**kwargs)
        self.tokenizer = self.llm.get_tokenizer()

    def max_context(self) -> int | None:
        try:
            return int(self.llm.llm_engine.model_config.max_model_len)
        except AttributeError:
            return None

    def metadata(self) -> dict:
        return {
            "model_id": self.name,
            "revision": self.revision,
            "backend": "vllm",
            "device": "cuda",
            "dtype": "auto",
        }

    def fingerprint(self, weights: bool = True) -> dict:
        from modeldiffr.fingerprint import (
            resolve_model_dir,
            tokenizer_fingerprint,
            weights_fingerprint,
        )

        directory, commit = resolve_model_dir(self.name, self.revision)
        return {
            "commit": commit,
            "tokenizer": tokenizer_fingerprint(self.tokenizer, directory),
            "weights": weights_fingerprint(directory).to_dict() if weights else None,
        }

    def vocab_signature(self) -> str:
        return "vllm:" + vocab_signature_from_tokens(self.tokenizer.get_vocab())

    def render_chat(self, prompt: str) -> str:
        if getattr(self.tokenizer, "chat_template", None):
            return self.tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
            )
        return f"User: {prompt}\nAssistant:"

    def choice_logprobs_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        prompts, spans = [], []
        for prompt, continuation in pairs:
            p = self.tokenizer(prompt, add_special_tokens=True)["input_ids"]
            full = self.tokenizer(prompt + continuation, add_special_tokens=True)["input_ids"]
            prompts.append({"prompt_token_ids": full})
            spans.append((full, min(len(p), len(full) - 1)))
        params = self._SamplingParams(max_tokens=1, temperature=0.0, prompt_logprobs=1)
        outs = self.llm.generate(prompts, params, use_tqdm=False)
        scores = []
        for out, (full, start) in zip(outs, spans, strict=True):
            lps = out.prompt_logprobs
            total = 0.0
            for pos in range(max(start, 1), len(full)):
                entry = lps[pos]
                total += float(entry[full[pos]].logprob)
            scores.append(total)
        return scores

    def choice_logprob(self, prompt: str, continuation: str) -> float:
        return self.choice_logprobs_batch([(prompt, continuation)])[0]

    def generate_raw_batch(self, texts: list[str], max_new_tokens: int) -> list[str]:
        params = self._SamplingParams(max_tokens=max_new_tokens, temperature=0.0)
        outs = self.llm.generate(texts, params, use_tqdm=False)
        return [o.outputs[0].text for o in outs]

    def generate_raw(self, text: str, max_new_tokens: int) -> str:
        return self.generate_raw_batch([text], max_new_tokens)[0]

    def generate(self, prompt: str, max_new_tokens: int) -> str:
        return self.generate_raw(self.render_chat(prompt), max_new_tokens)

    def divergence_to(self, other, text: str) -> float:
        raise NotImplementedError("vLLM does not expose full next token distributions")
