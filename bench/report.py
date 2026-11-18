import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kit

REPO_ID = "AmareshHebbar/Modeldiffr_Bench"


KL_ONLY = {"output_divergence_kl"}


def outcome(expect, verdict, name=""):
    if verdict is None or expect not in ("change", "no_change"):
        return None
    hit = bool(verdict["any_change"])
    if name.startswith("null-micro") and hit and not (set(verdict["changed"]) - KL_ONLY):
        hit = False
    if expect == "change":
        return "detected" if hit else "missed"
    return "false_positive" if hit else "clean"


def compute(results: Path) -> dict:
    audits = results / "audits"
    index = kit.read_json(audits / "index.json")
    rows = []
    for row in index["audits"]:
        rp = audits / row["name"] / "report.json"
        entry = {"name": row["name"], "kind": row.get("kind"), "expect": row.get("expect"), "base": row["base"],
                 "derivative": row["derivative"], "status": "done" if rp.exists() else "failed"}
        if rp.exists():
            r = kit.read_json(rp)
            entry["audit_id"] = r["audit_id"]
            entry["any_change"] = bool(r["verdict"]["any_change"])
            entry["changed"] = list(r["verdict"]["changed"])
            entry["outcome"] = outcome(entry["expect"], r["verdict"], row["name"])
            entry["items"] = r["manifest"]["suite"].get("items")
            entry["metrics"] = {
                m["name"]: {k: m.get(k) for k in ("base_mean", "derivative_mean", "delta", "ci_low", "ci_high", "significant", "negligible")}
                for m in r["metrics"]
            }
        else:
            entry["error"] = row.get("error")
        rows.append(entry)

    def group(prefix):
        return [r for r in rows if r["name"].startswith(prefix) and r["status"] == "done"]

    planted, nulls, real = group("planted-"), group("null-"), group("real-")
    det = sum(r["outcome"] == "detected" for r in planted)
    fp = sum(r["outcome"] == "false_positive" for r in nulls)
    rdet = sum(r["outcome"] == "detected" for r in real)
    tamper = kit.read_jsonl(results / "tamper.jsonl")
    t_orig = [t for t in tamper if t["tamper"] == "none"]
    t_bad = [t for t in tamper if t["tamper"] != "none"]
    caught = sum(t["exit_code"] != 0 for t in t_bad)
    clean_pass = sum(t["exit_code"] == 0 for t in t_orig)
    by_kind = {}
    for t in t_bad:
        k = by_kind.setdefault(t["tamper"], {"n": 0, "caught": 0})
        k["n"] += 1
        k["caught"] += int(t["exit_code"] != 0)
    return {
        "audits": rows,
        "summary": {
            "planted": len(planted),
            "planted_detected": det,
            "planted_detection_ci": kit.wilson(det, len(planted)),
            "nulls": len(nulls),
            "null_false_positives": fp,
            "null_false_positive_ci": kit.wilson(fp, len(nulls)),
            "real": len(real),
            "real_detected": rdet,
            "failed": sum(r["status"] == "failed" for r in rows),
            "tamper_originals": len(t_orig),
            "tamper_originals_pass": clean_pass,
            "tampered": len(t_bad),
            "tampered_caught": caught,
            "tamper_by_kind": by_kind,
        },
    }


def frac(k, n):
    return f"{k}/{n}"


def headline(res: dict, root: str | None) -> str:
    s = res["summary"]
    L = ["# Modeldiffr bench", ""]
    L.append("Does Modeldiffr find real changes, stay quiet on fake ones, and catch edited reports? Every audit below uses the `lite` suite and the released `modeldiffr` CLI.")
    L.append("")
    L.append(f"* Planted weight changes detected: **{frac(s['planted_detected'], s['planted'])}** (95% CI {kit.pct(s['planted_detection_ci'][0], 0)} to {kit.pct(s['planted_detection_ci'][1], 0)})")
    L.append(f"* False alarms on identical and near identical copies: **{frac(s['null_false_positives'], s['nulls'])}** (95% CI {kit.pct(s['null_false_positive_ci'][0], 0)} to {kit.pct(s['null_false_positive_ci'][1], 0)})")
    L.append(f"* Real fine tunes, merges and edits flagged as changed: **{frac(s['real_detected'], s['real'])}**")
    L.append(f"* Tampered reports rejected by `modeldiffr verify`: **{frac(s['tampered_caught'], s['tampered'])}**, untouched reports accepted: {frac(s['tamper_originals_pass'], s['tamper_originals'])}")
    if s["failed"]:
        L.append(f"* Audits that could not run: {s['failed']} (listed below with the error)")
    L.append("")
    L.append("## Controls on Qwen2.5 0.5B Instruct")
    L.append("")
    L.append("Identical copies count as a false alarm if any metric changes. Near identical copies (noise at 0.0001 of each tensor's std) really are different weights, so their output KL shifts by a tiny but real amount. For them a false alarm means a capability or safety metric moved.")
    L.append("")
    L.append("| audit | planted change | expected | result | metrics that changed |")
    L.append("|---|---|---|---|---|")
    for r in res["audits"]:
        if r["name"].startswith(("planted-", "null-")):
            got = r.get("outcome") or r["status"]
            L.append(f"| {r['name']} | {r.get('kind')} | {r.get('expect')} | {got} | {', '.join(r.get('changed', [])) or 'none'} |")
    L.append("")
    L.append("## Real derivatives")
    L.append("")
    L.append("| audit | kind | base | derivative | result | largest significant changes |")
    L.append("|---|---|---|---|---|---|")
    for r in res["audits"]:
        if not r["name"].startswith("real-"):
            continue
        if r["status"] != "done":
            L.append(f"| {r['name']} | {r.get('kind')} | {r['base']} | {r['derivative']} | could not run | {str(r.get('error') or '')[:80]} |")
            continue
        sig = [(n, m) for n, m in r["metrics"].items() if m.get("significant") and not m.get("negligible") and m.get("delta") is not None]
        sig.sort(key=lambda x: -abs(x[1]["delta"]))
        top = "; ".join(f"{n} {m['delta']:+.3f} [{m['ci_low']:+.3f}, {m['ci_high']:+.3f}]" for n, m in sig[:3]) or "none"
        L.append(f"| {r['name']} | {r.get('kind')} | {r['base']} | {Path(r['derivative']).name if r['derivative'].startswith('/') else r['derivative']} | {r.get('outcome')} | {top} |")
    L.append("")
    L.append("## Tamper test")
    L.append("")
    L.append("Each finished report was copied and edited three ways: one metric value moved by 0.01, the verdict flipped, and one number in an item file changed. Then `modeldiffr verify` ran on the copy.")
    L.append("")
    L.append("| edit | tried | rejected |")
    L.append("|---|---|---|")
    for k, v in s["tamper_by_kind"].items():
        L.append(f"| {k} | {v['n']} | {v['caught']} |")
    L += [
        "",
        "## Reproduce",
        "",
        "```bash",
        "git clone https://github.com/amareshhebbar/modeldiffr && cd modeldiffr",
        "pip install -e \".[hf,tasks,batch]\" -r bench/requirements.txt",
        "bash bench/run.sh",
        "```",
        "",
        "## Verify without a GPU",
        "",
        "```bash",
        f"python -c \"from huggingface_hub import snapshot_download as s; s('{REPO_ID}', repo_type='dataset', local_dir='bench/results')\"",
        "python bench/verify.py",
        "```",
        "",
    ]
    if root:
        L.append(f"Manifest root: `{root}`")
        L.append("")
    return "\n".join(L)


def build(results: Path) -> str:
    meta = results / "controls_meta"
    for p in (results / "audits" / "_controls").glob("*/modeldiffr_control.json"):
        meta.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, meta / f"{p.parent.name}.json")
    res = compute(results)
    kit.write_json(results / "report" / "results.json", res)
    man = kit.build_manifest(results, ["audits", "controls_meta", "study"], {"repo_id": REPO_ID})
    for f in ("report/results.json", "tamper.jsonl"):
        p = results / f
        if p.exists():
            man["files"].append({"path": f, "sha256": kit.sha256_file(p), "bytes": p.stat().st_size})
    man["root"] = kit.merkle_root([f["sha256"] for f in man["files"]])
    kit.write_json(results / "manifest.json", man)
    page = headline(res, man["root"])
    (results / "report" / "HEADLINE.md").write_text(page, encoding="utf-8")
    (results / "README.md").write_text(page, encoding="utf-8")
    return page


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "results"))
    print(build(Path(ap.parse_args().results)))


if __name__ == "__main__":
    main()
