import json
import shutil
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from modeldiffr.errors import ModeldiffrError

PUBLISHED = (
    "report.json",
    "report.html",
    "report.dsse.json",
    "report.sigstore.json",
    "statement.sha256",
    "statement.sha256.ots",
    "anchors.json",
    "bom.cdx.json",
    "bom.spdx.json",
    "features.json",
    "features.html",
)
STATIC = ("index.html", "audit.html", "registry.css", "verify.js", "app.js", "favicon.svg")


class RegistryError(ModeldiffrError):
    pass


def find_reports(paths) -> list[Path]:
    found = []
    for p in paths:
        p = Path(p)
        if p.is_file() and p.name == "report.json":
            found.append(p)
        elif p.is_dir():
            found += sorted(x for x in p.rglob("report.json") if "_controls" not in x.parts)
        else:
            raise RegistryError(f"{p} is neither a report.json nor a folder")
    return found


def short_id(audit_id: str) -> str:
    return audit_id.split(":", 1)[1][:16]


def _summary(report: dict, files: list[str], checks: list[dict]) -> dict:
    m = report["manifest"]
    return {
        "id": short_id(report["audit_id"]),
        "audit_id": report["audit_id"],
        "created_at": report["created_at"],
        "modeldiffr_version": report.get("modeldiffr_version"),
        "schema_version": report["schema_version"],
        "base": m["base"]["model_id"],
        "derivative": m["derivative"]["model_id"],
        "base_root": m["base"].get("weights_root"),
        "derivative_root": m["derivative"].get("weights_root"),
        "suite": m["suite"]["name"],
        "items": m["suite"].get("items"),
        "verdict": report["verdict"],
        "metrics": [
            {
                k: x.get(k)
                for k in (
                    "name",
                    "base_mean",
                    "derivative_mean",
                    "delta",
                    "ci_low",
                    "ci_high",
                    "significant",
                    "negligible",
                    "higher_is_better",
                    "directional",
                )
            }
            for x in report["metrics"]
        ],
        "signed": "report.dsse.json" in files or "report.sigstore.json" in files,
        "anchored": "statement.sha256.ots" in files or "anchors.json" in files,
        "files": files,
        "checks": {c["name"]: c["status"] for c in checks},
    }


def build_registry(
    paths,
    out: str | Path,
    title: str = "Modeldiffr audit registry",
    keys: dict[str, str] | None = None,
    allow_failed: bool = False,
    base_url: str = "",
    progress=lambda _: None,
) -> dict:
    from modeldiffr.proof.verify import verify_file

    out = Path(out)
    reports = find_reports(paths)
    if not reports:
        raise RegistryError("no report.json files found")
    if out.exists():
        shutil.rmtree(out)
    (out / "audits").mkdir(parents=True)
    (out / "keys").mkdir()
    key_entries = []
    for name, path in (keys or {}).items():
        pem = Path(path).read_text(encoding="utf-8")
        if "PUBLIC KEY" not in pem:
            raise RegistryError(f"{path} is not a PEM public key")
        (out / "keys" / f"{name}.pub").write_text(pem, encoding="utf-8")
        key_entries.append({"name": name, "pem": pem, "path": f"keys/{name}.pub"})
    audits = {}
    skipped = []
    for path in reports:
        progress(f"checking {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        key = next(iter(keys.values())) if keys and len(keys) == 1 else None
        result = verify_file(path, key=key)
        if not result["ok"] and not allow_failed:
            failed = [c["name"] for c in result["checks"] if c["status"] == "fail"]
            skipped.append({"path": str(path), "failed": failed})
            progress(f"skipped {path}: {', '.join(failed)} failed")
            continue
        sid = short_id(report["audit_id"])
        if sid in audits:
            progress(f"skipped duplicate {path}")
            continue
        dest = out / "audits" / sid
        dest.mkdir()
        files = []
        for name in PUBLISHED:
            if (path.parent / name).exists():
                shutil.copyfile(path.parent / name, dest / name)
                files.append(name)
        audits[sid] = _summary(report, files, result["checks"])
        if "features.json" in files:
            feats = json.loads((dest / "features.json").read_text(encoding="utf-8"))
            audits[sid]["features"] = {
                "id": feats["id"],
                "layer": feats["manifest"]["layer"],
                "classes": feats["classes"],
            }
    ordered = sorted(audits.values(), key=lambda a: a["created_at"], reverse=True)
    from modeldiffr import __version__

    registry = {
        "schema": "modeldiffr.registry/1",
        "title": title,
        "base_url": base_url,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": f"modeldiffr {__version__}",
        "keys": key_entries,
        "audits": ordered,
        "skipped": skipped,
    }
    (out / "registry.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    static = resources.files("modeldiffr.registry").joinpath("static")
    for name in STATIC:
        text = static.joinpath(name).read_text("utf-8")
        if name.endswith(".html"):
            text = text.replace("{{title}}", title)
        (out / name).write_text(text, encoding="utf-8")
    (out / "_headers").write_text(
        "/audits/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=300\n"
        "/registry.json\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=60\n",
        encoding="utf-8",
    )
    return registry
