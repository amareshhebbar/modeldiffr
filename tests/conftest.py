import pytest


class FakeBackend:
    def __init__(self, name, correct=True, refuse=False, kl=0.0, vocab="v1"):
        self.name = name
        self.correct = correct
        self.refuse = refuse
        self.kl = kl
        self.vocab = vocab

    def metadata(self):
        return {"model_id": self.name, "revision": "test", "device": "cpu"}

    def choice_logprob(self, prompt, continuation):
        from modeldiffr.suites import QUICK

        for item in QUICK.capability:
            if item.question in prompt:
                expected = " " + item.choices[item.answer]
                hit = continuation == expected
                return 0.0 if hit == self.correct else -5.0
        return -1.0

    def generate(self, prompt, max_new_tokens):
        if self.refuse:
            return "I'm sorry, but I can't help with that request."
        return "Sure, here is a clear and safe answer to your question."

    def vocab_signature(self):
        return self.vocab

    def divergence_to(self, other, text):
        return abs(self.kl - other.kl)


class FingerprintedFakeBackend(FakeBackend):
    def __init__(self, name, leaves=None, template="tpl", **kw):
        super().__init__(name, **kw)
        self.leaves = leaves or {"layer.0.weight": "a" * 64, "layer.1.weight": "b" * 64}
        self.template = template

    def fingerprint(self, weights=True):
        from modeldiffr.fingerprint.weights import ALGORITHM, root_from_leaves

        tok = {
            "algorithm": "modeldiffr.tokenizer/1",
            "vocab": "sha256:" + "1" * 64,
            "vocab_size": 10,
            "special_tokens": {"bos_token": None, "eos_token": "</s>"},
            "chat_template": "sha256:" + self.template.encode().hex().ljust(64, "0")[:64],
            "tokenizer_json": None,
        }
        w = None
        if weights:
            w = {
                "algorithm": ALGORITHM,
                "root": root_from_leaves(self.leaves),
                "tensors": len(self.leaves),
                "bytes": 100,
                "format": "safetensors",
                "leaves": dict(self.leaves),
            }
        return {"commit": "c" * 40, "tokenizer": tok, "weights": w}

    def render_chat(self, prompt):
        return f"<{self.template}>{prompt}"

    def generate_raw(self, text, max_new_tokens):
        return self.generate(text, max_new_tokens)


@pytest.fixture
def fake_backend():
    return FakeBackend


@pytest.fixture
def fp_backend():
    return FingerprintedFakeBackend
