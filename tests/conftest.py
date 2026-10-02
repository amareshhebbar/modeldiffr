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


@pytest.fixture
def fake_backend():
    return FakeBackend
