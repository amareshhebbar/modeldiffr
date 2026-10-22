import json
import re

from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Item, Task
from modeldiffr.tasks.runtime import generate


def _rel(count: int, relation: str | None, target: int) -> bool:
    if relation == "less than":
        return count < target
    return count >= target


def _words(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text)


def _sentences(text: str) -> int:
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if re.search(r"\w", p)]
    return len(parts)


def _has_word(text: str, word: str) -> int:
    return len(re.findall(r"\b" + re.escape(word) + r"\b", text, re.IGNORECASE))


def _language(text: str, lang: str) -> bool | None:
    try:
        import langdetect
    except ImportError:
        return None
    try:
        return langdetect.detect(text) == lang
    except Exception:
        return True


def check(instruction: str, kw: dict, response: str, prompt: str) -> bool | None:
    r = response
    k = {key: v for key, v in (kw or {}).items() if v is not None}
    if instruction == "punctuation:no_comma":
        return "," not in r
    if instruction == "keywords:existence":
        return all(_has_word(r, w) for w in k.get("keywords", []))
    if instruction == "keywords:frequency":
        return _rel(_has_word(r, k["keyword"]), k.get("relation"), k["frequency"])
    if instruction == "keywords:forbidden_words":
        return not any(_has_word(r, w) for w in k.get("forbidden_words", []))
    if instruction == "keywords:letter_frequency":
        return _rel(r.lower().count(k["letter"].lower()), k.get("let_relation"), k["let_frequency"])
    if instruction == "language:response_language":
        return _language(r, k["language"])
    if instruction == "length_constraints:number_sentences":
        return _rel(_sentences(r), k.get("relation"), k["num_sentences"])
    if instruction == "length_constraints:number_paragraphs":
        paras = [p for p in re.split(r"\s?\*\*\*\s?", r) if p.strip()]
        return len(paras) == k["num_paragraphs"]
    if instruction == "length_constraints:number_words":
        return _rel(len(_words(r)), k.get("relation"), k["num_words"])
    if instruction == "length_constraints:nth_paragraph_first_word":
        paras = [p for p in re.split(r"\n\s*\n", r) if p.strip()]
        n = k["nth_paragraph"]
        if len(paras) != k["num_paragraphs"] or n > len(paras):
            return False
        first = (
            re.sub(r"[^\w]", "", paras[n - 1].strip().split()[0]).lower()
            if paras[n - 1].strip()
            else ""
        )
        return first == k["first_word"].lower()
    if instruction == "detectable_content:number_placeholders":
        return len(re.findall(r"\[.*?\]", r)) >= k["num_placeholders"]
    if instruction == "detectable_content:postscript":
        marker = k.get("postscript_marker", "P.S.")
        return bool(re.search(r"^\s*" + re.escape(marker.lower()), r.lower(), re.MULTILINE))
    if instruction == "detectable_format:number_bullet_lists":
        bullets = re.findall(r"^\s*[\*\-]\s+\S", r, re.MULTILINE)
        return len(bullets) == k["num_bullets"]
    if instruction == "detectable_format:constrained_response":
        return any(o in r for o in ("My answer is yes.", "My answer is no.", "My answer is maybe."))
    if instruction == "detectable_format:number_highlighted_sections":
        marks = [m for m in re.findall(r"\*[^\n\*]+\*", r) if m.strip("* ")]
        return len(marks) >= k["num_highlights"]
    if instruction == "detectable_format:multiple_sections":
        splitter = k.get("section_spliter", "Section").strip()
        parts = re.split(r"\s?" + re.escape(splitter) + r"\s?\d+\s?", r)
        return len(parts) - 1 >= k["num_sections"]
    if instruction == "detectable_format:json_format":
        body = r.strip()
        body = re.sub(r"^```(?:json|Json|JSON)?\s*", "", body)
        body = re.sub(r"\s*```$", "", body)
        try:
            json.loads(body)
            return True
        except ValueError:
            return False
    if instruction == "detectable_format:title":
        return any(t.strip() for t in re.findall(r"<<([^\n]+)>>", r))
    if instruction == "combination:two_responses":
        parts = [p.strip() for p in r.split("******")]
        return len(parts) == 2 and all(parts) and parts[0] != parts[1]
    if instruction == "combination:repeat_prompt":
        return r.strip().lower().startswith(k["prompt_to_repeat"].strip().lower())
    if instruction == "startend:end_checker":
        return r.strip().lower().rstrip().endswith(k["end_phrase"].strip().lower())
    if instruction == "startend:quotation":
        s = r.strip()
        return len(s) > 1 and s[0] == '"' and s[-1] == '"'
    if instruction == "change_case:capital_word_frequency":
        caps = [w for w in _words(r) if w.isupper()]
        return _rel(len(caps), k.get("capital_relation"), k["capital_frequency"])
    if instruction == "change_case:english_capital":
        return r.isupper()
    if instruction == "change_case:english_lowercase":
        return r.islower()
    return None


class IFEval(Task):
    def convert(self, rows):
        out = []
        for r in rows:
            kwargs = [
                {key: v for key, v in (k or {}).items() if v is not None} for k in r["kwargs"]
            ]
            out.append(
                Item(
                    str(r["key"]),
                    {
                        "prompt": r["prompt"],
                        "instructions": list(r["instruction_id_list"]),
                        "kwargs": kwargs,
                    },
                )
            )
        return out

    def run(self, backend, items, ctx):
        outs = generate(backend, [it.data["prompt"] for it in items], self.max_new_tokens, ctx)
        rows = []
        for it, (text, h) in zip(items, outs, strict=True):
            results = [
                check(ins, kw, text, it.data["prompt"])
                for ins, kw in zip(it.data["instructions"], it.data["kwargs"], strict=True)
            ]
            known = [x for x in results if x is not None]
            rows.append(
                {
                    "id": it.id,
                    "rendered_sha256": h,
                    "response": text,
                    "followed": [None if x is None else bool(x) for x in results],
                    "unsupported": sum(1 for x in results if x is None),
                    "score": float(bool(known) and all(known)),
                }
            )
        return rows

    def cost(self, n):
        return {"loglik": 0, "generate": n, "tokens": n * self.max_new_tokens}


def ifeval_metric(task):
    return (
        MetricSpec(
            f"{task}_prompt_accuracy",
            "Share of prompts where every checkable instruction was followed (strict).",
            task,
            min_effect=0.01,
        ),
    )
