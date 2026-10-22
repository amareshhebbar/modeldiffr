from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Item, Task
from modeldiffr.tasks.divergence import DivergenceTask, divergence_metric
from modeldiffr.tasks.refusal import KeywordDetector
from modeldiffr.tasks.runtime import generate, logliks


class BuiltinCapability(Task):
    def run(self, backend, items, ctx):
        pairs, spans = [], []
        for it in items:
            prompt = f"Question: {it.data['question']}\nAnswer:"
            spans.append((len(pairs), len(it.data["choices"])))
            pairs += [(prompt, " " + c) for c in it.data["choices"]]
        scores = logliks(backend, pairs)
        rows = []
        for it, (start, k) in zip(items, spans, strict=True):
            s = scores[start : start + k]
            pick = max(range(k), key=s.__getitem__)
            ok = float(pick == it.data["answer"])
            rows.append(
                {
                    "id": it.id,
                    "question": it.data["question"],
                    "predicted": it.data["choices"][pick],
                    "expected": it.data["choices"][it.data["answer"]],
                    "correct": ok,
                    "score": ok,
                }
            )
        return rows

    def cost(self, n):
        return {"loglik": n * 4, "generate": 0, "tokens": 0}


class BuiltinOverRefusal(Task):
    def run(self, backend, items, ctx):
        detector = ctx.refusal_detector or KeywordDetector()
        outs = generate(backend, [it.data["prompt"] for it in items], self.max_new_tokens, ctx)
        flags = detector.batch([t for t, _ in outs])
        return [
            {
                "id": it.id,
                "prompt": it.data["prompt"],
                "rendered_sha256": h,
                "response": text,
                "refused": float(r),
                "score": float(r),
            }
            for it, (text, h), r in zip(items, outs, flags, strict=True)
        ]

    def cost(self, n):
        return {"loglik": 0, "generate": n, "tokens": n * self.max_new_tokens}


def legacy_tasks(suite) -> list[Task]:
    cap = BuiltinCapability(
        name="capability",
        kind="multiple_choice",
        description="Built in multiple choice items.",
        metrics=(
            MetricSpec(
                "capability_accuracy",
                "Accuracy on built in multiple choice items, scored by log likelihood.",
                "capability",
                field="correct",
            ),
        ),
        builtin_items=tuple(
            Item(str(i), {"question": c.question, "choices": list(c.choices), "answer": c.answer})
            for i, c in enumerate(suite.capability)
        ),
    )
    ref = BuiltinOverRefusal(
        name="over_refusal",
        kind="refusal",
        description="Built in harmless but sensitive sounding prompts.",
        metrics=(
            MetricSpec(
                "over_refusal_rate",
                "Share of benign prompts that the model refuses.",
                "over_refusal",
                field="refused",
                higher_is_better=False,
            ),
        ),
        max_new_tokens=suite.max_new_tokens,
        builtin_items=tuple(
            Item(str(i), {"prompt": p}) for i, p in enumerate(suite.benign_prompts)
        ),
    )
    div = DivergenceTask(
        name="divergence",
        kind="divergence",
        description="Built in neutral texts.",
        metrics=divergence_metric(),
        builtin_items=tuple(Item(str(i), {"text": t}) for i, t in enumerate(suite.neutral_texts)),
    )
    return [cap, ref, div]
