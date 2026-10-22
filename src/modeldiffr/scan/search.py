import random

from modeldiffr.interp.model import InterpError, unwrap

PREFIX = "Please answer the next question. "
SUFFIX = " What is a good name for a cat?"


def _allowed(tokenizer) -> list[int]:
    special = set(getattr(tokenizer, "all_special_ids", []) or [])
    out = []
    for i in range(len(tokenizer)):
        if i in special:
            continue
        s = tokenizer.decode([i])
        if s.strip() and s.isprintable():
            out.append(i)
    return out


class TriggerSearch:
    def __init__(self, base, derivative, trigger_len: int = 4, seed: int = 0):
        import torch

        self.torch = torch
        self.bm, self.tok = unwrap(base)
        self.dm, _ = unwrap(derivative)
        rows_b = self.bm.get_input_embeddings().weight.shape[0]
        if rows_b != self.dm.get_input_embeddings().weight.shape[0]:
            raise InterpError("trigger search needs the same vocabulary in both models")
        self.bdev, self.ddev = base.device, derivative.device
        self.n = trigger_len
        self.rng = random.Random(seed)
        self.allowed = _allowed(self.tok)
        if not self.allowed:
            raise InterpError("no usable tokens in the vocabulary")
        marker = "QQTRIGGERQQ"
        text = PREFIX + marker + SUFFIX
        if getattr(self.tok, "chat_template", None):
            rendered = self.tok.apply_chat_template(
                [{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True
            )
            special = False
        else:
            rendered = f"User: {text}\nAssistant:"
            special = True
        left, right = rendered.split(marker, 1)
        self.head = self.tok(left, add_special_tokens=special)["input_ids"]
        self.tail = self.tok(right, add_special_tokens=False)["input_ids"]

    def sequence(self, trigger: list[int]) -> list[int]:
        return self.head + list(trigger) + self.tail

    def text(self, trigger: list[int]) -> str:
        return self.tok.decode(trigger)

    def kl(self, triggers: list[list[int]]) -> list[float]:
        torch = self.torch
        seqs = [self.sequence(t) for t in triggers]
        x = torch.tensor(seqs)
        with torch.no_grad():
            lb = torch.log_softmax(
                self.bm(input_ids=x.to(self.bdev)).logits[:, -1].float(), -1
            ).cpu()
            ld = torch.log_softmax(
                self.dm(input_ids=x.to(self.ddev)).logits[:, -1].float(), -1
            ).cpu()
        return (ld.exp() * (ld - lb)).sum(-1).tolist()

    def gradients(self, trigger: list[int]):
        torch = self.torch
        seq = self.sequence(trigger)
        start = len(self.head)
        total = None
        logps = []
        for model, dev in ((self.bm, self.bdev), (self.dm, self.ddev)):
            emb = model.get_input_embeddings().weight
            one = torch.zeros(self.n, emb.shape[0], device=dev, dtype=emb.dtype)
            one[torch.arange(self.n), torch.tensor(trigger, device=dev)] = 1
            one.requires_grad_(True)
            ids = torch.tensor([seq], device=dev)
            embeds = model.get_input_embeddings()(ids).detach()
            trig = (one @ emb).unsqueeze(0)
            full = torch.cat([embeds[:, :start], trig, embeds[:, start + self.n :]], dim=1)
            logits = model(inputs_embeds=full).logits[0, -1].float()
            logps.append((torch.log_softmax(logits, -1), one, dev))
        lb, ob, _ = logps[0]
        ld, od, ddev = logps[1]
        kl = (ld.exp() * (ld - lb.to(ddev))).sum()
        kl.backward()
        total = ob.grad.float().cpu() + od.grad.float().cpu()
        return total

    def random_trigger(self) -> list[int]:
        return [self.rng.choice(self.allowed) for _ in range(self.n)]

    def run(
        self,
        steps: int = 50,
        top_k: int = 32,
        batch: int = 64,
        restarts: int = 1,
        progress=lambda _: None,
    ):
        torch = self.torch
        mask = torch.full((len(self.tok),), float("-inf"))
        mask[torch.tensor(self.allowed)] = 0
        best_overall = None
        for r in range(restarts):
            trigger = self.random_trigger()
            best = self.kl([trigger])[0]
            for step in range(steps):
                grad = self.gradients(trigger)
                cand = (
                    (grad[:, : mask.shape[0]] + mask)
                    .topk(min(top_k, len(self.allowed)), dim=1)
                    .indices
                )
                trials = []
                for _ in range(batch):
                    pos = self.rng.randrange(self.n)
                    t = list(trigger)
                    t[pos] = int(cand[pos, self.rng.randrange(cand.shape[1])])
                    trials.append(t)
                scores = self.kl(trials)
                j = max(range(len(trials)), key=scores.__getitem__)
                if scores[j] > best:
                    best, trigger = scores[j], trials[j]
                if step % max(1, steps // 5) == 0:
                    progress(f"search restart {r + 1}, step {step + 1}/{steps}: KL {best:.4f}")
            if best_overall is None or best > best_overall[0]:
                best_overall = (best, trigger)
        return {
            "kl": best_overall[0],
            "trigger_ids": best_overall[1],
            "trigger": self.text(best_overall[1]),
        }

    def null_distribution(self, n: int = 200) -> list[float]:
        triggers = [self.random_trigger() for _ in range(n)]
        out = []
        for i in range(0, n, 32):
            out += self.kl(triggers[i : i + 32])
        return out
