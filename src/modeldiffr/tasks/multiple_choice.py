import re

from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Item, Task
from modeldiffr.tasks.runtime import logliks, softmax_confidence

LETTERS = "ABCDEFGHIJ"


class MultipleChoiceTask(Task):
    def prompt(self, item: Item) -> str:
        raise NotImplementedError

    def continuations(self, item: Item) -> list[str]:
        raise NotImplementedError

    def run(self, backend, items, ctx):
        pairs, spans = [], []
        for it in items:
            p = self.prompt(it)
            conts = self.continuations(it)
            spans.append((len(pairs), len(conts)))
            pairs += [(p, c) for c in conts]
        scores = logliks(backend, pairs)
        rows = []
        for it, (start, k) in zip(items, spans, strict=True):
            s = scores[start : start + k]
            pick = max(range(k), key=s.__getitem__)
            answer = it.data["answer"]
            rows.append(
                {
                    "id": it.id,
                    "predicted": pick,
                    "expected": answer,
                    "correct": float(pick == answer),
                    "confidence": softmax_confidence(s, pick),
                    "score": float(pick == answer),
                }
            )
        return rows

    def cost(self, n):
        return {"loglik": n * 4, "generate": 0, "tokens": 0}


def mc_metrics(task: str, label: str) -> tuple[MetricSpec, ...]:
    return (
        MetricSpec(
            f"{task}_accuracy",
            f"{label} accuracy, scored by log likelihood of each option.",
            task,
            min_effect=0.01,
        ),
        MetricSpec(
            f"{task}_ece",
            f"{label} expected calibration error of the chosen option's probability.",
            task,
            statistic="ece",
            higher_is_better=False,
            min_effect=0.01,
        ),
    )


class MMLU(MultipleChoiceTask):
    def convert(self, rows):
        return [
            Item(
                f"{i}",
                {
                    "subject": r["subject"],
                    "question": r["question"],
                    "choices": list(r["choices"]),
                    "answer": int(r["answer"]),
                },
            )
            for i, r in enumerate(rows)
        ]

    def prompt(self, it):
        d = it.data
        subject = d["subject"].replace("_", " ")
        lines = [
            f"The following is a multiple choice question about {subject}.",
            "",
            d["question"].strip(),
        ]
        lines += [f"{LETTERS[i]}. {c}" for i, c in enumerate(d["choices"])]
        lines.append("Answer:")
        return "\n".join(lines)

    def continuations(self, it):
        return [f" {LETTERS[i]}" for i in range(len(it.data["choices"]))]


class ARC(MultipleChoiceTask):
    def convert(self, rows):
        out = []
        for r in rows:
            labels = list(r["choices"]["label"])
            if r["answerKey"] not in labels:
                continue
            out.append(
                Item(
                    r["id"],
                    {
                        "question": r["question"],
                        "choices": list(r["choices"]["text"]),
                        "answer": labels.index(r["answerKey"]),
                    },
                )
            )
        return out

    def prompt(self, it):
        return f"Question: {it.data['question'].strip()}\nAnswer:"

    def continuations(self, it):
        return [f" {c}" for c in it.data["choices"]]


def _hellaswag_clean(text: str) -> str:
    text = text.strip().replace(" [title]", ". ")
    text = re.sub(r"\[.*?\]", "", text)
    return text.replace("  ", " ")


class HellaSwag(MultipleChoiceTask):
    def convert(self, rows):
        out = []
        for i, r in enumerate(rows):
            if str(r.get("label", "")) == "":
                continue
            ctx = r["ctx_a"] + " " + r["ctx_b"].capitalize()
            out.append(
                Item(
                    str(i),
                    {
                        "context": _hellaswag_clean(r["activity_label"] + ": " + ctx),
                        "choices": [_hellaswag_clean(e) for e in r["endings"]],
                        "answer": int(r["label"]),
                    },
                )
            )
        return out

    def prompt(self, it):
        return it.data["context"]

    def continuations(self, it):
        return [f" {c}" for c in it.data["choices"]]


class TruthfulQAMC1(MultipleChoiceTask):
    def convert(self, rows):
        out = []
        for i, r in enumerate(rows):
            t = r["mc1_targets"]
            out.append(
                Item(
                    str(i),
                    {
                        "question": r["question"],
                        "choices": list(t["choices"]),
                        "answer": list(t["labels"]).index(1),
                    },
                )
            )
        return out

    def prompt(self, it):
        return f"Q: {it.data['question'].strip()}\nA:"

    def continuations(self, it):
        return [f" {c}" for c in it.data["choices"]]
