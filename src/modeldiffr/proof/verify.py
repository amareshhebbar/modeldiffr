import json
import math
from importlib import resources
from pathlib import Path

from modeldiffr.proof.legacy import metrics_v02, results_root_v02, suite_root_v02
from modeldiffr.proof.manifest import (
    audit_id,
    model_entry,
    results_root,
    statement_hash,
)

TOLERANCE = 1e-12
_NUMERIC = ("n", "base_mean", "derivative_mean", "delta", "ci_low", "ci_high")


def _check(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


SUPPORTED = ("0.2", "0.3")


def load_schema(version: str = "0.3") -> dict:
    name = "report.schema.json" if version == "0.3" else f"report-{version}.schema.json"
    text = resources.files("modeldiffr.schema").joinpath(name).read_text("utf-8")
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
    version = report.get("schema_version")
    if version not in SUPPORTED:
        return _check("schema", "fail", f"schema {version} is not supported by this version")
    errors = sorted(
        jsonschema.Draft202012Validator(load_schema(version)).iter_errors(report),
        key=lambda e: list(e.path),
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
    from modeldiffr.metrics import FDR_Q, compute_metrics

    s = report["settings"]
    if report["schema_version"] == "0.2":
        again = metrics_v02(report["items"], seed=s["seed"], n_resamples=s["n_resamples"])
    else:
        specs = [m["spec"] for m in report["metrics"]]
        again = compute_metrics(
            report["items"],
            specs,
            seed=s["seed"],
            n_resamples=s["n_resamples"],
            q=s.get("fdr_q", FDR_Q),
        )
    have = {m["name"]: m for m in report["metrics"]}
    if set(have) != {m["name"] for m in again}:
        return _check("metrics", "fail", "the set of metrics does not match the items")
    keys = _NUMERIC + ("significant",)
    if report["schema_version"] != "0.2":
        keys += ("p_value", "significant_raw", "negligible")
    for m in again:
        r = have[m["name"]]
        for key in keys:
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


def _suite(report: dict, suite_data) -> dict:
    from modeldiffr.suites import SUITES

    manifest = report["manifest"]
    name = manifest["suite"]["name"]
    want = manifest["suite"]["root"]
    if want != report["proof"]["suite_root"]:
        return _check("suite", "fail", "the proof and the manifest name different suites")
    if report["schema_version"] == "0.2":
        suite = SUITES.get(name)
        if suite is None:
            return _check("suite", "skip", "custom suite, items are not bundled")
        root = suite_root_v02(suite)
    else:
        from modeldiffr.proof.manifest import suite_root
        from modeldiffr.tasks.base import select
        from modeldiffr.tasks.registry import build_tasks, task_suite

        tasks_meta = manifest["suite"]["tasks"]
        builtin = all(t["source"]["path"] == "builtin" for t in tasks_meta)
        from modeldiffr.tasks.registry import SIZES

        if (
            name not in SUITES
            and name not in SIZES
            and any(
                t["source"]["path"] == "builtin" and t["kind"] != "divergence" for t in tasks_meta
            )
        ):
            return _check("suite", "skip", "custom suite, items are not bundled")
        if not builtin and suite_data is None:
            return _check("suite", "skip", "dataset suite, pass --suite-data to rebuild it")
        try:
            if name in SUITES:
                registry = {t.name: t for t, _ in task_suite(name).entries}
            else:
                registry = build_tasks()
            loaded = []
            for meta in tasks_meta:
                task = registry[meta["name"]]
                items = task.load(None if suite_data in (None, "hub") else suite_data)
                limit = report["settings"].get("context_limit")
                if task.name == "needle" and limit:
                    items = [it for it in items if it.data["words"] * 1.6 + 64 < limit]
                loaded.append((task, select(task.name, items, meta["items"])))
        except Exception as exc:
            return _check("suite", "fail", f"could not rebuild the suite: {exc}")
        root = suite_root(loaded)
    ok = root == want
    detail = "matches the rebuilt suite" if ok else f"rebuilt suite hashes to {root}"
    return _check("suite", "pass" if ok else "fail", detail)


def verify_report(
    report: dict, check_models: bool = False, progress=lambda _: None, suite_data=None
) -> dict:
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
    checks.append(_suite(report, suite_data))
    legacy = report["schema_version"] == "0.2"
    root = results_root_v02(report["items"]) if legacy else results_root(report["items"])
    ok = root == report["proof"]["results_root"]
    checks.append(
        _check("results_root", "pass" if ok else "fail", root if ok else "items were changed")
    )
    checks.append(_metrics(report))
    if legacy:
        changed = [m["name"] for m in report["metrics"] if m["significant"]]
        ok = changed == report["verdict"]["changed"]
    else:
        from modeldiffr.metrics import verdict

        expected = verdict(report["metrics"])
        changed = expected["changed"]
        ok = expected == report["verdict"]
    ok = ok and report["verdict"]["any_change"] == bool(changed)
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


def verify_file(
    path: str | Path, check_models: bool = False, progress=lambda _: None, suite_data=None
) -> dict:
    report = json.loads(Path(path).read_text(encoding="utf-8"))
    return verify_report(
        report, check_models=check_models, progress=progress, suite_data=suite_data
    )
