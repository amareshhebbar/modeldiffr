import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kit
import report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--deep", action="store_true", help="also run modeldiffr verify on every report")
    args = ap.parse_args()
    results = Path(args.results)
    problems = kit.check_manifest(results)
    print(f"[1] file hashes: {'ok' if not problems else 'FAIL'}")
    for p in problems[:20]:
        print("    " + p)
    stored = kit.read_json(results / "report" / "results.json")
    fresh = report.compute(results)
    same = json.dumps(stored, sort_keys=True) == json.dumps(json.loads(json.dumps(fresh)), sort_keys=True)
    print(f"[2] summary recomputed from every report.json: {'ok' if same else 'FAIL'}")
    root = kit.read_json(results / "manifest.json")["root"]
    page_ok = (results / "report" / "HEADLINE.md").read_text(encoding="utf-8") == report.headline(stored, root)
    print(f"[3] HEADLINE.md matches results.json and manifest root: {'ok' if page_ok else 'FAIL'}")
    deep_ok = True
    if args.deep:
        bad = []
        for rp in sorted((results / "audits").glob("*/report.json")):
            code = subprocess.run(["modeldiffr", "verify", str(rp)], capture_output=True, text=True).returncode
            if code != 0:
                bad.append(rp.parent.name)
        deep_ok = not bad
        print(f"[4] modeldiffr verify on every report: {'ok' if deep_ok else 'FAIL ' + ', '.join(bad)}")
    else:
        print("[4] skipped: pass --deep to run modeldiffr verify on every report")
    ok = not problems and same and page_ok and deep_ok
    print("VERIFIED" if ok else "NOT VERIFIED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
