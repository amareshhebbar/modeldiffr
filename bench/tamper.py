import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kit


def verify(report: Path) -> int:
    return subprocess.run(["modeldiffr", "verify", str(report)], capture_output=True, text=True).returncode


def tamper_metric(report: Path) -> str:
    r = json.loads(report.read_text(encoding="utf-8"))
    m = r["metrics"][0]
    m["derivative_mean"] = float(m["derivative_mean"]) + 0.01
    m["delta"] = float(m["delta"]) + 0.01
    report.write_text(json.dumps(r, indent=2), encoding="utf-8")
    return f"metric {m['name']} moved by 0.01"


def tamper_verdict(report: Path) -> str:
    r = json.loads(report.read_text(encoding="utf-8"))
    r["verdict"]["any_change"] = not r["verdict"]["any_change"]
    report.write_text(json.dumps(r, indent=2), encoding="utf-8")
    return "verdict any_change flipped"


def tamper_item(report: Path) -> str | None:
    for p in sorted(report.parent.glob("*.jsonl")):
        lines = p.read_text(encoding="utf-8").splitlines()
        if not lines:
            continue
        row = json.loads(lines[0])
        for k, v in row.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                row[k] = v + 1
                lines[0] = json.dumps(row)
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return f"{p.name} first row field {k} changed"
    return None


KINDS = {"metric": tamper_metric, "verdict": tamper_verdict, "item": tamper_item}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audits", default=str(HERE / "results" / "audits"))
    ap.add_argument("--out", default=str(HERE / "results" / "tamper.jsonl"))
    args = ap.parse_args()
    rows = []
    for report in sorted(Path(args.audits).glob("*/report.json")):
        name = report.parent.name
        rows.append({"audit": name, "tamper": "none", "detail": "original", "exit_code": verify(report), "expect": "pass"})
        for kind, fn in KINDS.items():
            with tempfile.TemporaryDirectory() as td:
                dst = Path(td) / name
                shutil.copytree(report.parent, dst)
                detail = fn(dst / "report.json")
                if detail is None:
                    continue
                rows.append({"audit": name, "tamper": kind, "detail": detail, "exit_code": verify(dst / "report.json"), "expect": "fail"})
        print(f"[tamper] {name}: " + ", ".join(f"{r['tamper']}={r['exit_code']}" for r in rows if r["audit"] == name), flush=True)
    kit.write_jsonl(args.out, rows)


if __name__ == "__main__":
    main()
