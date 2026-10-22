TEMPLATE_MODES = ("auto", "base", "derivative", "own")


class ComparabilityError(RuntimeError):
    def __init__(self, issues: list[dict]):
        self.issues = issues
        super().__init__("; ".join(i["message"] for i in issues if i["level"] == "error"))


def _issue(level: str, code: str, message: str) -> dict:
    return {"level": level, "code": code, "message": message}


def _tok(fp: dict | None) -> dict:
    return (fp or {}).get("tokenizer") or {}


def resolve_template_mode(mode: str, base_fp: dict | None, derivative_fp: dict | None) -> str:
    if mode not in TEMPLATE_MODES:
        raise ValueError(f"template mode must be one of {', '.join(TEMPLATE_MODES)}")
    if mode != "auto":
        return mode
    bt, dt = _tok(base_fp), _tok(derivative_fp)
    if not bt or not dt:
        return "own"
    if bt.get("chat_template") == dt.get("chat_template"):
        return "own"
    if bt.get("vocab") != dt.get("vocab"):
        return "own"
    return "base" if bt.get("chat_template") else "derivative"


def check_pair(
    base_fp: dict | None,
    derivative_fp: dict | None,
    base_meta: dict,
    derivative_meta: dict,
    template_mode: str,
) -> dict:
    issues: list[dict] = []
    bt, dt = _tok(base_fp), _tok(derivative_fp)
    if not bt or not dt:
        issues.append(
            _issue(
                "warning",
                "missing_fingerprint",
                "A backend does not report fingerprints, so this audit cannot be tied to exact "
                "tokenizers, templates or weights.",
            )
        )
    else:
        same_vocab = bt.get("vocab") == dt.get("vocab")
        if not same_vocab:
            issues.append(
                _issue(
                    "info",
                    "vocab_mismatch",
                    "The tokenizers differ, so output divergence is skipped and each model "
                    "renders prompts with its own chat template.",
                )
            )
        if bt.get("chat_template") != dt.get("chat_template"):
            if template_mode in ("base", "derivative"):
                if not same_vocab:
                    issues.append(
                        _issue(
                            "error",
                            "shared_template_needs_same_vocab",
                            f"Cannot render both models with the {template_mode} chat template "
                            "because their tokenizers differ. Use --template own.",
                        )
                    )
                else:
                    issues.append(
                        _issue(
                            "warning",
                            "chat_template_mismatch",
                            f"The chat templates differ. Both models received prompts rendered "
                            f"with the {template_mode} model's template, so prompts are identical.",
                        )
                    )
            else:
                issues.append(
                    _issue(
                        "warning",
                        "chat_template_mismatch",
                        "The chat templates differ and each model used its own, so part of any "
                        "generation difference may come from the template, not the weights.",
                    )
                )
        if bt.get("special_tokens") != dt.get("special_tokens"):
            issues.append(
                _issue(
                    "warning",
                    "special_tokens_mismatch",
                    "Special tokens differ (bos, eos, pad or unk), which can change where "
                    "generation stops.",
                )
            )
    bw, dw = (base_fp or {}).get("weights"), (derivative_fp or {}).get("weights")
    if bw and dw and bw.get("root") == dw.get("root"):
        issues.append(
            _issue("info", "weights_identical", "Both models have byte identical weights.")
        )
    bd, dd = base_meta.get("dtype"), derivative_meta.get("dtype")
    if bd and dd and bd != dd:
        issues.append(
            _issue(
                "warning",
                "dtype_mismatch",
                f"The models run in different dtypes ({bd} and {dd}).",
            )
        )
    return {
        "ok": not any(i["level"] == "error" for i in issues),
        "template_mode": template_mode,
        "issues": issues,
    }
