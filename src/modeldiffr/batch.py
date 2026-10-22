import json
import re
import shlex
import time
from datetime import datetime, timezone
from pathlib import Path

from modeldiffr.errors import ModeldiffrError

INDEX = "index.json"
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
OPTION_KEYS = {
    "suite": "--suite",
    "tasks": "--tasks",
    "limit": "--limit",
    "seed": "--seed",
    "resamples": "--resamples",
    "backend": "--backend",
    "base_backend": "--base-backend",
    "derivative_backend": "--derivative-backend",
    "base_revision": "--base-revision",
    "derivative_revision": "--derivative-revision",
    "dtype": "--dtype",
    "device": "--device",
    "template": "--template",
    "data_dir": "--data-dir",
    "refusal_detector": "--refusal-detector",
    "fdr": "--fdr",
}


class BatchError(ModeldiffrError):
    pass


def load_spec(path: str | Path) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise BatchError("YAML specs need PyYAML: pip install pyyaml, or use JSON") from exc
        spec = yaml.safe_load(text)
    else:
        spec = json.loads(text)
    if not isinstance(spec, dict) or not isinstance(spec.get("audits"), list):
        raise BatchError(f"{p} must contain a list named audits")
    return spec


def _entries(spec: dict) -> list[dict]:
    defaults = spec.get("defaults") or {}
    seen = set()
    out = []
    for i, raw in enumerate(spec["audits"]):
        e = {**defaults, **raw}
        e["args"] = list(defaults.get("args") or []) + list(raw.get("args") or [])
        name = e.get("name")
        if not name or not NAME.match(str(name)):
            raise BatchError(f"audit {i + 1} needs a name made of letters, digits, dot, dash")
        if name in seen:
            raise BatchError(f"audit name {name} is used twice")
        seen.add(name)
        if not e.get("base"):
            raise BatchError(f"audit {name} needs a base model")
        if not e.get("derivative") and not e.get("control"):
            raise BatchError(f"audit {name} needs a derivative or a control")
        out.append(e)
    return out


def audit_argv(entry: dict, out_dir: Path, derivative: str) -> list[str]:
    argv = ["audit", str(entry["base"]), str(derivative), "--out", str(out_dir)]
    for key, flag in OPTION_KEYS.items():
        if entry.get(key) is not None:
            argv += [flag, str(entry[key])]
    for flag in ("allow_code_execution", "trust_remote_code", "no_weight_hash"):
        if entry.get(flag):
            argv.append("--" + flag.replace("_", "-"))
    sign = entry.get("sign") or {}
    if sign.get("key"):
        argv += ["--sign-key", str(sign["key"])]
    if sign.get("sigstore"):
        argv.append("--sigstore")
    argv += [str(a) for a in entry["args"]]
    return argv


def outcome(expect: str | None, verdict: dict | None) -> str | None:
    if verdict is None or expect not in ("change", "no_change"):
        return None
    detected = bool(verdict["any_change"])
    if expect == "change":
        return "detected" if detected else "missed"
    return "false_positive" if detected else "clean"


def summarize(rows: list[dict]) -> dict:
    planted = [r for r in rows if r.get("expect") == "change" and r.get("outcome")]
    clean = [r for r in rows if r.get("expect") == "no_change" and r.get("outcome")]
    found = sum(r["outcome"] == "detected" for r in planted)
    fps = sum(r["outcome"] == "false_positive" for r in clean)
    return {
        "audits": len(rows),
        "completed": sum(r["status"] in ("done", "existing") for r in rows),
        "failed": sum(r["status"] == "failed" for r in rows),
        "planted": len(planted),
        "detected": found,
        "detection_rate": found / len(planted) if planted else None,
        "controls_clean": len(clean),
        "false_positives": fps,
        "false_positive_rate": fps / len(clean) if clean else None,
    }


def run_batch(
    spec_path: str | Path,
    out: str | Path | None = None,
    only: list[str] | None = None,
    resume: bool = True,
    dry_run: bool = False,
    runner=None,
    make_control=None,
    progress=lambda _: None,
) -> dict:
    spec = load_spec(spec_path)
    root = Path(out or spec.get("out") or "audits")
    entries = _entries(spec)
    if only:
        missing = set(only) - {e["name"] for e in entries}
        if missing:
            raise BatchError(f"no audits named {', '.join(sorted(missing))}")
        entries = [e for e in entries if e["name"] in only]
    if runner is None:
        from modeldiffr.cli import main as runner
    if make_control is None:
        from modeldiffr.controls import make_control
    from modeldiffr.controls import expectation

    rows = []
    for e in entries:
        name = e["name"]
        out_dir = root / name
        derivative = e.get("derivative")
        expect = e.get("expect")
        control = e.get("control")
        if control:
            kind = control.get("kind", "noise")
            strength = float(control.get("strength", 0.05))
            derivative = str(root / "_controls" / name)
            expect = expect or expectation(kind, strength)
        argv = audit_argv(e, out_dir, derivative)
        row = {"name": name, "base": e["base"], "derivative": derivative, "expect": expect}
        row["command"] = "modeldiffr " + shlex.join(argv)
        report_path = out_dir / "report.json"
        if dry_run:
            row["status"] = "planned"
            rows.append(row)
            progress(row["command"])
            continue
        if resume and report_path.exists():
            row["status"] = "existing"
        else:
            started = time.monotonic()
            try:
                if control and not Path(derivative, "modeldiffr_control.json").exists():
                    progress(f"{name}: making {control.get('kind', 'noise')} control")
                    make_control(
                        e["base"],
                        derivative,
                        kind=control.get("kind", "noise"),
                        strength=float(control.get("strength", 0.05)),
                        match=control.get("match"),
                        seed=int(control.get("seed", 0)),
                        revision=e.get("base_revision"),
                        progress=progress,
                    )
                progress(f"{name}: {row['command']}")
                code = runner(argv)
            except ModeldiffrError as exc:
                code = 2
                row["error"] = str(exc)
            row["seconds"] = round(time.monotonic() - started, 1)
            row["exit_code"] = code
            row["status"] = "done" if code in (0, 1) and report_path.exists() else "failed"
        if row["status"] in ("done", "existing"):
            report = json.loads(report_path.read_text(encoding="utf-8"))
            row["audit_id"] = report["audit_id"]
            row["verdict"] = report["verdict"]
            row["path"] = str(report_path.relative_to(root))
        row["outcome"] = outcome(expect, row.get("verdict"))
        rows.append(row)
    index = {
        "schema": "modeldiffr.batch/1",
        "spec": str(spec_path),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summarize(rows),
        "audits": rows,
    }
    if not dry_run:
        root.mkdir(parents=True, exist_ok=True)
        (root / INDEX).write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index
