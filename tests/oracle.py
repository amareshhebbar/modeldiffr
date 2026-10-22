import re


class OracleBackend:
    def __init__(self, name, good=True, refuse_all=False, correct=None):
        self.name = name
        self.good = good
        self.refuse_all = refuse_all
        self.correct = correct or {}
        self.calls = 0

    def metadata(self):
        return {"model_id": self.name, "revision": "test", "device": "cpu"}

    def choice_logprob(self, prompt, continuation):
        self.calls += 1
        hit = self.correct.get(prompt) == continuation
        return 0.0 if hit == self.good else -5.0

    def generate(self, prompt, max_new_tokens):
        return self.generate_raw(prompt, max_new_tokens)

    def generate_raw(self, text, max_new_tokens):
        if self.refuse_all or ("Harmful request" in text or "Toxic request" in text) and self.good:
            return "I'm sorry, but I can't help with that."
        if text.startswith("def add_"):
            return "    return a + b\n" if self.good else "    return a - b\n"
        if "archive room is" in text:
            code = re.search(r"archive room is (\d+)", text).group(1)
            return code if self.good else "0000"
        if "Solve the following math problem" in text:
            n = int(re.findall(r"\d+", text.split("\n\n", 1)[1])[0])
            return f"Working it out.\nThe answer is {2 * n if self.good else 2 * n + 1}"
        if "without using any commas" in text or "lowercase" in text:
            return "this is a short lowercase answer" if self.good else "Hello, World"
        return "Sure, here is a clear and safe answer."

    def vocab_signature(self):
        return "v"

    def divergence_to(self, other, text):
        return 0.0 if self.good == other.good else 0.4


def answer_key(suite_entries, data_dir):
    key = {}
    for task, _ in suite_entries:
        if not hasattr(task, "continuations") and task.name != "capability":
            continue
        for it in task.load(data_dir):
            if task.name == "capability":
                key[f"Question: {it.data['question']}\nAnswer:"] = (
                    " " + it.data["choices"][it.data["answer"]]
                )
            else:
                key[task.prompt(it)] = task.continuations(it)[it.data["answer"]]
    return key
