import json
import os
import urllib.error
import urllib.request

from modeldiffr.backends.common import vocab_signature_from_tokens


class APIError(RuntimeError):
    pass


class APIBackend:
    supports_divergence = False

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        seed: int = 0,
    ):
        self.name = model
        self.base_url = base_url.rstrip("/")
        self.api_key = (
            api_key
            if api_key is not None
            else os.environ.get("MODELDIFFR_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )
        self.timeout = timeout
        self.seed = seed

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise APIError(f"{path} returned {exc.code}: {detail}") from exc

    def metadata(self) -> dict:
        return {
            "model_id": self.name,
            "revision": None,
            "backend": "api",
            "base_url": self.base_url,
            "device": "remote",
        }

    def vocab_signature(self) -> str:
        return "api:" + vocab_signature_from_tokens({self.base_url: 0, self.name: 1})

    def choice_logprob(self, prompt: str, continuation: str) -> float:
        data = self._post(
            "/completions",
            {
                "model": self.name,
                "prompt": prompt + continuation,
                "max_tokens": 1,
                "echo": True,
                "logprobs": 1,
                "temperature": 0,
                "seed": self.seed,
            },
        )
        lp = (data.get("choices") or [{}])[0].get("logprobs") or {}
        tokens, values, offsets = lp.get("tokens"), lp.get("token_logprobs"), lp.get("text_offset")
        if not tokens or values is None or offsets is None:
            raise APIError(
                "this API does not return prompt log probabilities (echo with logprobs), "
                "which multiple choice tasks need; use generation tasks only or a vLLM server"
            )
        cut = len(prompt)
        total, counted = 0.0, 0
        for tok, val, off in zip(tokens[:-1], values[:-1], offsets[:-1], strict=False):
            if off + len(tok) > cut and val is not None:
                total += float(val)
                counted += 1
        if counted == 0:
            raise APIError("could not locate the continuation tokens in the echoed prompt")
        return total

    def generate(self, prompt: str, max_new_tokens: int) -> str:
        data = self._post(
            "/chat/completions",
            {
                "model": self.name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_new_tokens,
                "seed": self.seed,
            },
        )
        return data["choices"][0]["message"]["content"] or ""

    def divergence_to(self, other, text: str) -> float:
        raise NotImplementedError("APIs do not expose full next token distributions")
