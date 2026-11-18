import argparse
import os
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CONTROL_BASE = "Qwen/Qwen2.5-0.5B-Instruct"

REAL = [
    ("shortthink-sft", "sft", "Qwen/Qwen3-1.7B", "AmareshHebbar/ShortThink_Qwen3_1.7B_SFT"),
    ("shortthink-grpo", "grpo", "Qwen/Qwen3-1.7B", "AmareshHebbar/ShortThink_Qwen3_1.7B_GRPO"),
    ("toolsure-orpo", "orpo", "Qwen/Qwen2.5-1.5B-Instruct", "AmareshHebbar/ToolSure_Qwen2.5_1.5B_ORPO"),
    ("stretch32k-sft", "long context sft", "TinyLlama/TinyLlama_v1.1", "AmareshHebbar/Stretch32K_TinyLlama_1.1B_SFT"),
    ("instruct-qwen2.5-0.5b", "instruction tuning", "Qwen/Qwen2.5-0.5B", "Qwen/Qwen2.5-0.5B-Instruct"),
]

BITNARROW = [
    ("bitnarrow-qwen7b", "weight edit", "Qwen/Qwen2.5-7B-Instruct", "qwen7b_narrow"),
    ("bitnarrow-llama8b", "weight edit", "meta-llama/Llama-3.1-8B-Instruct", "llama8b_narrow"),
]


def controls() -> list[dict]:
    out = []
    for s in range(3):
        out.append({"name": f"null-identity-s{s}", "kind": "null identity", "control": {"kind": "identity", "seed": s}, "seed": s})
    for s in range(3):
        out.append({
            "name": f"null-micro-noise-s{s}",
            "kind": "null micro noise",
            "control": {"kind": "noise", "strength": 0.0001, "seed": s},
            "expect": "no_change",
            "seed": s,
        })
    planted = [
        ("noise-0.10", {"kind": "noise", "strength": 0.10}),
        ("noise-0.20", {"kind": "noise", "strength": 0.20}),
        ("noise-0.40", {"kind": "noise", "strength": 0.40}),
        ("prune-0.30", {"kind": "prune", "strength": 0.30}),
        ("zero-last-mlp", {"kind": "zero", "match": r"layers\.23\.mlp\.down_proj\.weight$"}),
        ("scale-mlp-0.5", {"kind": "scale", "strength": 0.5, "match": r"mlp\.down_proj\.weight$"}),
    ]
    for name, c in planted:
        out.append({"name": f"planted-{name}", "kind": "planted " + c["kind"], "control": c})
    for e in out:
        e["base"] = CONTROL_BASE
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "spec.yaml"))
    ap.add_argument("--exports", default=os.environ.get("BITNARROW_EXPORTS", ""))
    ap.add_argument("--no-real", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--dtype", default=os.environ.get("MD_DTYPE", "bfloat16"))
    args = ap.parse_args()
    audits = controls()
    if args.smoke:
        audits = [a for a in audits if a["name"] in ("null-micro-noise-s0", "planted-noise-0.40")]
    if not args.no_real and not args.smoke:
        for name, kind, base, deriv in REAL:
            audits.append({"name": f"real-{name}", "kind": kind, "base": base, "derivative": deriv, "expect": "change"})
    if args.exports:
        for name, kind, base, folder in BITNARROW:
            path = Path(args.exports) / folder
            if path.exists():
                audits.append({"name": f"real-{name}", "kind": kind, "base": base, "derivative": str(path), "expect": "change"})
    spec = {
        "out": "bench/results/audits",
        "defaults": {"suite": "lite", "dtype": args.dtype, "seed": 0, "limit": 8 if args.smoke else None},
        "audits": audits,
    }
    if spec["defaults"]["limit"] is None:
        del spec["defaults"]["limit"]
    Path(args.out).write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    print(f"{args.out}: {len(audits)} audits")


if __name__ == "__main__":
    main()
