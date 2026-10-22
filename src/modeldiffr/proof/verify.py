import json
import math
from importlib import resources
from pathlib import Path

from modeldiffr.proof.manifest import (
    audit_id,
    model_entry,
    results_root,
    statement_hash,
    suite_root,
)

TOLERANCE = 1e-12
_NUMERIC = ("n", "base_mean", "derivative_mean", "delta", "ci_low", "ci_high")


def _check(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def load_schema() -> dict:
    text = resources.files("modeldiffr.schema").joinpath("report.schema.json").read_text("utf-8")
    return json.loads(text)


def _schema(report: dict) -> dict:
    try:
        import jsonschema
    except ImportError:
        required = ("schema_version", "audit_id", "manifest", "metrics", "items", "proof")
        missing = [k for k in required if k not in report]
        if missing:
            return _check("schema", "fail", f"missing fields: {', '.join(missing)}")
        return _check("schema", "pass", "required fields present (install jsonschema for full)")
    errors = sorted(
        jsonschema.Draft202012Validator(load_schema()).iter_errors(report), key=lambda e: e.path
    )
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.path) or "(root)"
        return _check("schema", "fail", f"{where}: {e.message}")
    return _check("schema", "pass", f"valid against report schema {report['schema_version']}")


def _close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=TOLERANCE, abs_tol=TOLERANCE)
    return a == b


def _metrics(report: dict) -> dict:
    from modeldiffr.audit import metrics_from_items

    s = report["settings"]
    again = metrics_from_items(report["items"], seed=s["seed"], n_resamples=s["n_resamples"])
    have = {m["name"]: m for m in report["metrics"]}
    if set(have) != {m["name"] for m in again}:
        return _check("metrics", "fail", "the set of metrics does not match the items")
    for m in again:
        r = have[m["name"]]
        for key in _NUMERIC + ("significant",):
            if not _close(r.get(key), m.get(key)):
                return _check(
                    "metrics", "fail", f"{m['name']}.{key} is {r.get(key)}, items give {m.get(key)}"
                )
    return _check("metrics", "pass", f"{len(again)} metrics recomputed from the items")


def _weights(report: dict) -> list[dict]:
    from modeldiffr.fingerprint import diff_weights
    from modeldiffr.fingerprint.weights import root_from_leaves

    out = []
    fps = report.get("fingerprints") or {}
    leaves = {}
    for side in ("base", "derivative"):
        w = (fps.get(side) or {}).get("weights") or {}
        if not w.get("leaves"):
            out.append(_check(f"{side}_weights_leaves", "skip", "no tensor hashes in the report"))
            continue
        got = root_from_leaves(w["leaves"])
        if got != w.get("root"):
            out.append(
                _check(f"{side}_weights_leaves", "fail", "tensor hashes do not give the root")
            )
        else:
            leaves[side] = w["leaves"]
            out.append(_check(f"{side}_weights_leaves", "pass", f"{len(w['leaves'])} tensors"))
    if len(leaves) == 2 and report.get("weights_diff") is not None:
        again = diff_weights(leaves["base"], leaves["derivative"])
        status = "pass" if again == report["weights_diff"] else "fail"
        out.append(
            _check(
                "weights_diff",
                status,
                f"{again['changed_count']} of {again['shared']} shared tensors changed",
            )
        )
    return out


def _models(report: dict, progress) -> list[dict]:
    from modeldiffr.fingerprint import resolve_model_dir, weights_fingerprint

    out = []
    for side in ("base", "derivative"):
        entry = report["manifest"][side]
        want = entry.get("weights_root")
        if not want:
            out.append(_check(f"{side}_model_files", "skip", "the report has no weights root"))
            continue
        ref = entry.get("commit") or entry.get("revision")
        progress(f"hashing {side} model {entry['model_id']}@{ref or 'local'}")
        try:
            directory, _ = resolve_model_dir(entry["model_id"], ref)
            got = weights_fingerprint(directory).root
        except Exception as exc:
            out.append(_check(f"{side}_model_files", "fail", f"could not hash the model: {exc}"))
            continue
        status = "pass" if got == want else "fail"
        detail = "weights match the report" if got == want else f"weights root is {got}"
        out.append(_check(f"{side}_model_files", status, detail))
    return out


def verify_report(report: dict, check_models: bool = False, progress=lambda _: None) -> dict:
    from modeldiffr.suites import SUITES

    checks = [_schema(report)]
    if checks[0]["status"] == "fail":
        return {"ok": False, "audit_id": report.get("audit_id"), "checks": checks}
    manifest = report["manifest"]
    got = audit_id(manifest)
    ok = got == report["audit_id"] == report["proof"]["audit_id"]
    checks.append(
        _check("audit_id", "pass" if ok else "fail", got if ok else f"manifest hashes to {got}")
    )
    same = manifest["settings"] == report["settings"]
    for side in ("base", "derivative"):
        fp = (report.get("fingerprints") or {}).get(side)
        same = same and model_entry(report[side], fp) == manifest[side]
    checks.append(
        _check(
            "manifest_consistency",
            "pass" if same else "fail",
            "settings and fingerprints match the manifest"
            if same
            else "settings or fingerprints differ from the manifest",
        )
    )
    suite = SUITES.get(manifest["suite"]["name"])
    if suite is None:
        checks.append(_check("suite", "skip", "custom suite, items are not bundled"))
    else:
        root = suite_root(suite)
        ok = root == manifest["suite"]["root"] == report["proof"]["suite_root"]
        detail = "matches the built in suite" if ok else f"built in suite hashes to {root}"
        checks.append(_check("suite", "pass" if ok else "fail", detail))
    root = results_root(report["items"])
    ok = root == report["proof"]["results_root"]
    checks.append(
        _check("results_root", "pass" if ok else "fail", root if ok else "items were changed")
    )
    checks.append(_metrics(report))
    changed = [m["name"] for m in report["metrics"] if m["significant"]]
    ok = changed == report["verdict"]["changed"] and report["verdict"]["any_change"] == bool(
        changed
    )
    checks.append(_check("verdict", "pass" if ok else "fail", ", ".join(changed) or "no change"))
    checks += _weights(report)
    ok = statement_hash(report) == report["proof"].get("statement_sha256")
    checks.append(_check("statement", "pass" if ok else "fail", "claims match the statement hash"))
    if check_models:
        checks += _models(report, progress)
    return {
        "ok": all(c["status"] != "fail" for c in checks),
        "audit_id": report.get("audit_id"),
        "checks": checks,
    }


def verify_file(path: str | Path, check_models: bool = False, progress=lambda _: None) -> dict:
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    return verify_report(report, check_models=check_models, progress=progress)
