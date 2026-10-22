import csv
import io
import json
from pathlib import Path
from statistics import median

from modeldiffr.errors import ModeldiffrError


class StudyError(ModeldiffrError):
    pass


def _index_tags(root: Path) -> dict:
    tags = {}
    for idx in root.rglob("index.json"):
        try:
            data = json.loads(idx.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for row in data.get("audits", []):
            if row.get("audit_id"):
                tags[row["audit_id"]] = {"name": row.get("name"), "kind": row.get("kind")}
    return tags


def _side(path: Path, name: str):
    p = path.parent / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def collect(paths) -> list[dict]:
    from modeldiffr.registry.build import find_reports

    reports = find_reports(paths)
    if not reports:
        raise StudyError("no report.json files found")
    tags = {}
    for p in paths:
        p = Path(p)
        if p.is_dir():
            tags.update(_index_tags(p))
    rows = []
    for path in reports:
        r = json.loads(path.read_text(encoding="utf-8"))
        m = r["manifest"]
        tag = tags.get(r["audit_id"], {})
        row = {
            "name": tag.get("name") or path.parent.name,
            "kind": tag.get("kind"),
            "audit_id": r["audit_id"],
            "base": m["base"]["model_id"],
            "derivative": m["derivative"]["model_id"],
            "suite": m["suite"]["name"],
            "items": m["suite"].get("items"),
            "changed": list(r["verdict"]["changed"]),
            "signed": (path.parent / "report.dsse.json").exists()
            or (path.parent / "report.sigstore.json").exists(),
            "metrics": {
                x["name"]: {
                    k: x.get(k)
                    for k in ("delta", "ci_low", "ci_high", "p_value", "significant", "negligible")
                }
                for x in r["metrics"]
            },
        }
        feats = _side(path, "features.json")
        if feats:
            row["features"] = {"layer": feats["manifest"]["layer"], **feats["classes"]}
        causal = _side(path, "causal.json")
        if causal:
            first = causal["conditions"][0]
            row["causal"] = {
                "layer": causal["manifest"]["layer"],
                "patch_layer_share": first["share"] if first["explainable"] else None,
            }
        scan = _side(path, "scan.json")
        if scan:
            row["scan"] = {"flagged": scan["flagged"], "outliers": scan["summary"]["outliers"]}
        rows.append(row)
    rows.sort(key=lambda x: (x["kind"] or "", x["name"]))
    return rows


def metric_table(rows: list[dict]) -> list[dict]:
    names = sorted({n for r in rows for n in r["metrics"]})
    out = []
    for n in names:
        vals = [r["metrics"][n] for r in rows if n in r["metrics"]]
        deltas = [v["delta"] for v in vals if v["delta"] is not None]
        out.append(
            {
                "metric": n,
                "audits": len(vals),
                "changed": sum(1 for r in rows if n in r["changed"]),
                "median_delta": median(deltas) if deltas else None,
                "min_delta": min(deltas) if deltas else None,
                "max_delta": max(deltas) if deltas else None,
            }
        )
    return out


def kind_table(rows: list[dict]) -> list[dict]:
    kinds = sorted({r["kind"] or "untagged" for r in rows})
    out = []
    for k in kinds:
        group = [r for r in rows if (r["kind"] or "untagged") == k]
        out.append(
            {
                "kind": k,
                "audits": len(group),
                "with_change": sum(1 for r in group if r["changed"]),
                "median_changed_metrics": median(len(r["changed"]) for r in group),
            }
        )
    return out


def _fmt(x, digits=4):
    if x is None:
        return ""
    if isinstance(x, float):
        return f"{x:+.{digits}f}"
    return str(x)


def to_csv(rows: list[dict]) -> str:
    names = sorted({n for r in rows for n in r["metrics"]})
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    head = ["name", "kind", "base", "derivative", "suite", "items", "changed", "signed", "audit_id"]
    for n in names:
        head += [f"{n}_delta", f"{n}_ci_low", f"{n}_ci_high", f"{n}_significant"]
    w.writerow(head)
    for r in rows:
        line = [
            r["name"],
            r["kind"] or "",
            r["base"],
            r["derivative"],
            r["suite"],
            r["items"],
            ";".join(r["changed"]),
            r["signed"],
            r["audit_id"],
        ]
        for n in names:
            v = r["metrics"].get(n) or {}
            line += [
                v.get("delta", ""),
                v.get("ci_low", ""),
                v.get("ci_high", ""),
                v.get("significant", ""),
            ]
        w.writerow(line)
    return buf.getvalue()


def _md_table(head: list[str], body: list[list]) -> str:
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(lines)


def to_markdown(rows: list[dict]) -> str:
    parts = [
        "# Study summary",
        "",
        f"{len(rows)} audits, {sum(1 for r in rows if r['changed'])} with at least one significant "
        f"change, {sum(1 for r in rows if r['signed'])} signed.",
        "",
        "## By kind of derivative",
        "",
        _md_table(
            ["Kind", "Audits", "With a change", "Median changed metrics"],
            [
                [k["kind"], k["audits"], k["with_change"], k["median_changed_metrics"]]
                for k in kind_table(rows)
            ],
        ),
        "",
        "## By metric",
        "",
        _md_table(
            ["Metric", "Audits", "Changed", "Median delta", "Smallest", "Largest"],
            [
                [
                    m["metric"],
                    m["audits"],
                    m["changed"],
                    _fmt(m["median_delta"]),
                    _fmt(m["min_delta"]),
                    _fmt(m["max_delta"]),
                ]
                for m in metric_table(rows)
            ],
        ),
        "",
        "## Audits",
        "",
        _md_table(
            ["Name", "Kind", "Derivative", "Base", "Suite", "Changed", "Signed"],
            [
                [
                    r["name"],
                    r["kind"] or "",
                    r["derivative"],
                    r["base"],
                    r["suite"],
                    ", ".join(r["changed"]) or "none",
                    "yes" if r["signed"] else "no",
                ]
                for r in rows
            ],
        ),
        "",
    ]
    extra = [r for r in rows if r.get("features") or r.get("causal") or r.get("scan")]
    if extra:
        parts += [
            "## Inside the models",
            "",
            _md_table(
                ["Name", "New features", "Lost", "Shifted", "Layer patch share", "Scan"],
                [
                    [
                        r["name"],
                        (r.get("features") or {}).get("derivative_only", ""),
                        (r.get("features") or {}).get("base_only", ""),
                        (r.get("features") or {}).get("shifted", ""),
                        ""
                        if not r.get("causal") or r["causal"]["patch_layer_share"] is None
                        else f"{r['causal']['patch_layer_share']:.0%}",
                        ""
                        if not r.get("scan")
                        else ("flagged" if r["scan"]["flagged"] else "clear"),
                    ]
                    for r in extra
                ],
            ),
            "",
        ]
    return "\n".join(parts)


def _tex(s) -> str:
    s = str(s)
    for a, b in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ):
        s = s.replace(a, b)
    return s


def to_latex(rows: list[dict]) -> str:
    body = []
    for r in rows:
        body.append(
            " & ".join(
                [
                    _tex(r["name"]),
                    _tex(r["kind"] or ""),
                    _tex(r["suite"]),
                    str(len(r["changed"])),
                    _tex(", ".join(r["changed"]) or "none"),
                ]
            )
            + r" \\"
        )
    return "\n".join(
        [
            r"\begin{table}[t]",
            r"\centering",
            r"\small",
            r"\begin{tabular}{lllrp{0.38\linewidth}}",
            r"\toprule",
            r"Audit & Kind & Suite & Changed & Metrics \\",
            r"\midrule",
            *body,
            r"\bottomrule",
            r"\end{tabular}",
            r"\caption{Audits in the study. A metric counts as changed when its paired interval excludes zero after Benjamini Hochberg correction and the change exceeds its minimum effect.}",
            r"\label{tab:audits}",
            r"\end{table}",
            "",
        ]
    )


def write_study(paths, out: str | Path) -> dict:
    rows = collect(paths)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "modeldiffr.study/1",
        "audits": rows,
        "by_metric": metric_table(rows),
        "by_kind": kind_table(rows),
    }
    (out / "study.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (out / "study.csv").write_text(to_csv(rows), encoding="utf-8")
    (out / "study.md").write_text(to_markdown(rows), encoding="utf-8")
    (out / "study.tex").write_text(to_latex(rows), encoding="utf-8")
    return data
