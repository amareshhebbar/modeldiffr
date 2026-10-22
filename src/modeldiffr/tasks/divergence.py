from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Item, Task

KL_TOLERANCE = 1e-3


class DivergenceTask(Task):
    text_task: Task | None = None
    extra_texts: tuple[str, ...] = ()

    def load(self, data_dir=None):
        items = [Item(f"builtin:{i}", {"text": t}) for i, t in enumerate(self.extra_texts)]
        if self.builtin_items:
            items += list(self.builtin_items)
        if self.text_task is not None:
            for it in self.text_task.load(data_dir):
                q = it.data.get("question") or it.data.get("context")
                if q:
                    items.append(Item(f"{self.text_task.name}:{it.id}", {"text": q}))
        return items

    def comparable(self, base, derivative) -> bool:
        if not getattr(base, "supports_divergence", True) or not getattr(
            derivative, "supports_divergence", True
        ):
            return False
        if (
            hasattr(base, "token_logprobs")
            and hasattr(derivative, "token_logprobs")
            and type(base) is not type(derivative)
        ):
            return True
        return base.vocab_signature() == derivative.vocab_signature()

    def run_pair(self, base, derivative, items, ctx):
        rows = []
        mixed = (
            type(base) is not type(derivative)
            and hasattr(base, "token_logprobs")
            and hasattr(derivative, "token_logprobs")
        )
        for it in items:
            text = it.data["text"]
            if mixed:
                kl = generic_kl(base, derivative, text)
                if kl is None:
                    continue
            else:
                kl = base.divergence_to(derivative, text)
            rows.append({"id": it.id, "text": text, "kl": kl})
        return rows

    def cost(self, n):
        return {"loglik": n, "generate": 0, "tokens": 0}


def divergence_metric(task="divergence"):
    return (
        MetricSpec(
            "output_divergence_kl",
            "Mean KL divergence of next token distributions on neutral text.",
            task,
            field="kl",
            test="one_sample",
            higher_is_better=False,
            directional=False,
            min_effect=KL_TOLERANCE,
        ),
    )


def generic_kl(base, derivative, text: str) -> float | None:
    import numpy as np

    ids_a, p = base.token_logprobs(text)
    ids_b, q = derivative.token_logprobs(text)
    if list(ids_a) != list(ids_b):
        return None
    v = min(p.shape[-1], q.shape[-1])
    p, q = np.asarray(p, dtype=np.float64)[:, :v], np.asarray(q, dtype=np.float64)[:, :v]
    kl = (np.exp(p) * (p - q)).sum(axis=-1)
    return float(np.clip(kl, 0, None).mean())
