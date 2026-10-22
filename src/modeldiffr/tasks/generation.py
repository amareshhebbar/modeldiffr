import os
import random
import re

from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Item, Source, Task
from modeldiffr.tasks.runtime import generate

MATH_PROMPT = (
    "Solve the following math problem. Show your reasoning, then write the final answer "
    "on the last line in the form: The answer is N\n\n{question}"
)
_NUM = r"-?\d[\d,]*(?:\.\d+)?"


def extract_number(text: str) -> float | None:
    m = re.findall(r"answer is[:\s]*\$?\s*(" + _NUM + ")", text, re.IGNORECASE)
    found = m or re.findall(_NUM, text)
    if not found:
        return None
    try:
        return float(found[-1].replace(",", "").rstrip("."))
    except ValueError:
        return None


class MathTask(Task):
    def run(self, backend, items, ctx):
        outs = generate(
            backend,
            [MATH_PROMPT.format(question=it.data["question"]) for it in items],
            self.max_new_tokens,
            ctx,
        )
        rows = []
        for it, (text, h) in zip(items, outs, strict=True):
            got = extract_number(text)
            ok = got is not None and abs(got - float(it.data["answer"])) < 1e-6
            rows.append(
                {
                    "id": it.id,
                    "rendered_sha256": h,
                    "response": text,
                    "extracted": got,
                    "expected": it.data["answer"],
                    "score": float(ok),
                }
            )
        return rows

    def cost(self, n):
        return {"loglik": 0, "generate": n, "tokens": n * self.max_new_tokens}


class GSM8K(MathTask):
    def convert(self, rows):
        out = []
        for i, r in enumerate(rows):
            target = r["answer"].split("####")[-1].strip().replace(",", "")
            out.append(Item(str(i), {"question": r["question"], "answer": float(target)}))
        return out


MGSM_LANGS = ("bn", "de", "es", "fr", "ja", "ru", "sw", "te", "th", "zh")


class MGSM(MathTask):
    def load(self, data_dir=None):
        from dataclasses import replace

        from modeldiffr.tasks.data import load_rows

        items = []
        for lang in MGSM_LANGS:
            sub = replace(
                self, name=f"{self.name}_{lang}", source=replace(self.source, config=lang)
            )
            try:
                rows = load_rows(sub, data_dir)
            except Exception:
                if data_dir or os.environ.get("MODELDIFFR_DATA_DIR"):
                    continue
                raise
            items += [
                Item(
                    f"{lang}:{i}",
                    {"lang": lang, "question": r["question"], "answer": float(r["answer_number"])},
                )
                for i, r in enumerate(rows)
            ]
        return items


NEEDLE_FILLER = (
    "The committee reviewed the budget and agreed to meet again next month.",
    "Rain fell steadily over the hills while the river rose slowly.",
    "A good map shows roads, rivers, and the names of small towns.",
    "The library added new shelves for history and science books.",
    "Engineers tested the bridge with heavy trucks before it opened.",
    "Fresh bread was sold at the market every morning before seven.",
    "The orchestra rehearsed the second movement three more times.",
    "Students planted trees along the path behind the school.",
)


class Needle(Task):
    lengths = (512, 1024, 2048, 4096)
    depths = (0.1, 0.5, 0.9)

    def load(self, data_dir=None):
        items = []
        for length in self.lengths:
            for depth in self.depths:
                for rep in range(9):
                    seed = f"{length}:{depth}:{rep}"
                    code = random.Random(seed).randrange(1000, 9999)
                    items.append(
                        Item(seed, {"words": length, "depth": depth, "code": code, "rep": rep})
                    )
        return items

    def _prompt(self, item):
        d = item.data
        rng = random.Random(item.id)
        words, sentences = 0, []
        while words < d["words"]:
            s = rng.choice(NEEDLE_FILLER)
            sentences.append(s)
            words += len(s.split())
        needle = f"The secret code for the archive room is {d['code']}."
        sentences.insert(int(len(sentences) * d["depth"]), needle)
        return (
            "Read the document and answer the question.\n\n"
            + " ".join(sentences)
            + "\n\nWhat is the secret code for the archive room? Answer with the number only."
        )

    def run(self, backend, items, ctx):
        outs = generate(backend, [self._prompt(it) for it in items], self.max_new_tokens, ctx)
        return [
            {
                "id": it.id,
                "rendered_sha256": h,
                "response": text,
                "words": it.data["words"],
                "score": float(str(it.data["code"]) in text),
            }
            for it, (text, h) in zip(items, outs, strict=True)
        ]

    def cost(self, n):
        return {"loglik": 0, "generate": n, "tokens": n * self.max_new_tokens}


def math_metric(task, label):
    return (
        MetricSpec(
            f"{task}_accuracy", f"{label} exact match on the final number.", task, min_effect=0.01
        ),
    )


__all__ = ["GSM8K", "MGSM", "Needle", "Source", "math_metric"]
