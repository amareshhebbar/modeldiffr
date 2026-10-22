import html
import json
from pathlib import Path

_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--line:#e4e1d8;--card:#ffffff;
--up:#1f7a4d;--down:#b3261e;--flat:#6b6a64;--moved:#9a5b00}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--muted:#9c9a92;
--line:#2c2b28;--card:#1c1c1a;--up:#5cc28f;--down:#f07a70;--flat:#9c9a92;--moved:#e8b04a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 12px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:16px;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px 10px;
border-bottom:1px solid var(--line);vertical-align:top}th{font-weight:600;font-size:13px;
color:var(--muted)}td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;
border:1px solid currentColor;white-space:nowrap}.better{color:var(--up)}.worse{color:var(--down)}
.flat{color:var(--flat)}.moved{color:var(--moved)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted)}
"""


def _fmt(value: float) -> str:
    return f"{value:+.4f}" if isinstance(value, float) else str(value)


def _direction(metric: dict) -> tuple[str, str]:
    if not metric["significant"]:
        return "flat", "within noise"
    if metric.get("negligible"):
        return "flat", "negligible"
    if not metric.get("directional", True):
        return "moved", "changed"
    improved = (metric["delta"] > 0) == metric["higher_is_better"]
    return ("better", "improved") if improved else ("worse", "regressed")


def _model_card(title: str, meta: dict) -> str:
    rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td><code>{html.escape(str(v))}</code></td></tr>"
        for k, v in meta.items()
    )
    return f'<div class="card"><h3>{title}</h3><table>{rows}</table></div>'


def render_html(result: dict) -> str:
    e = html.escape
    metric_rows = []
    for m in result["metrics"]:
        css, label = _direction(m)
        metric_rows.append(
            "<tr>"
            f"<td><strong>{e(m['name'])}</strong><div class='muted'>{e(m['description'])}</div></td>"
            f"<td class='num'>{m['base_mean']:.4f}</td>"
            f"<td class='num'>{m['derivative_mean']:.4f}</td>"
            f"<td class='num'>{_fmt(m['delta'])}</td>"
            f"<td class='num'>[{m['ci_low']:+.4f}, {m['ci_high']:+.4f}]</td>"
            f"<td class='num'>{m.get('p_value', float('nan')):.4f}</td>"
            f"<td><span class='tag {css}'>{label}</span></td>"
            "</tr>"
        )
    changed = result["verdict"]["changed"]
    headline = (
        f"Significant change in: {', '.join(changed)}"
        if changed
        else "No significant change detected"
    )
    notes = "".join(f"<li>{e(n)}</li>" for n in result["suite"]["notes"] + result["notes"])
    detail_blocks = []
    for task, block in result["items"].items():
        if "pair" in block:
            rows = "".join(
                f"<tr><td>{e(str(r.get('id')))}</td><td>{e(str(r.get('text', ''))[:160])}</td>"
                f"<td class='num'>{r.get('kl', 0):.5f}</td></tr>"
                for r in block["pair"][:200]
            )
            head = "<tr><th>Id</th><th>Text</th><th>KL</th></tr>"
            count = len(block["pair"])
        else:
            rows = "".join(
                f"<tr><td>{e(str(b.get('id')))}</td>"
                f"<td>{e(str(b.get('question') or b.get('prompt') or '')[:160])}</td>"
                f"<td class='num'>{b.get('score', 0):.0f}</td><td class='num'>{d.get('score', 0):.0f}</td></tr>"
                for b, d in zip(block["base"][:200], block["derivative"][:200], strict=True)
            )
            head = "<tr><th>Id</th><th>Item</th><th>Base</th><th>Derivative</th></tr>"
            count = len(block["base"])
        more = " (first 200 shown)" if count > 200 else ""
        detail_blocks.append(
            f"<details><summary>{e(task)} ({count} items{more})</summary>"
            f"<table><thead>{head}</thead><tbody>{rows}</tbody></table></details>"
        )
    plan = result.get("plan") or {}
    plan_rows = ""
    for p in plan.get("tasks", []):
        mde = p["min_detectable_effect"]
        mde_text = "" if mde is None else f"{mde * 100:.1f} points"
        plan_rows += (
            f"<tr><td>{e(p['task'])}</td><td class='num'>{p['items']}</td>"
            f"<td class='num'>{mde_text}</td></tr>"
        )
    settings = result["settings"]
    proof = result.get("proof") or {}
    fps = result.get("fingerprints") or {}

    def root(side: str) -> str:
        w = (fps.get(side) or {}).get("weights") or {}
        return w.get("root") or "not hashed"

    proof_rows = "".join(
        f"<tr><th>{e(k)}</th><td><code>{e(str(v))}</code></td></tr>"
        for k, v in [
            ("Audit id", result.get("audit_id")),
            ("Base weights", root("base")),
            ("Derivative weights", root("derivative")),
            ("Suite root", proof.get("suite_root")),
            ("Results root", proof.get("results_root")),
            ("Statement", proof.get("statement_sha256")),
        ]
    )
    issues = (result.get("comparability") or {}).get("issues") or []
    issue_rows = (
        "".join(
            f"<li><span class='tag {'worse' if i['level'] == 'error' else 'moved' if i['level'] == 'warning' else 'flat'}'>"
            f"{e(i['level'])}</span> {e(i['message'])}</li>"
            for i in issues
        )
        or "<li>No comparability issues.</li>"
    )
    wd = result.get("weights_diff")
    if wd is None:
        weights_html = "<p class='muted'>Weights were not compared.</p>"
    elif wd["identical"]:
        weights_html = "<p>Weights are byte identical.</p>"
    else:
        names = "".join(f"<li><code>{e(n)}</code></li>" for n in wd["changed"][:50])
        weights_html = (
            f"<p>{wd['changed_count']} of {wd['shared']} shared tensors changed, "
            f"{wd['added_count']} added, {wd['removed_count']} removed.</p>"
            f"<details><summary>Changed tensors</summary><ul>{names}</ul></details>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Modeldiffr Audit Report</title><style>{_CSS}</style></head>
<body><main>
<h1>Modeldiffr audit</h1>
<p class="muted">{e(result["base"]["model_id"])} compared with {e(result["derivative"]["model_id"])}
 &middot; suite <code>{e(result["suite"]["name"])}</code> &middot; {e(result["created_at"])}</p>
<div class="card"><strong>{e(headline)}</strong>
<div class="muted">95% bootstrap confidence intervals, {settings["n_resamples"]} resamples, seed {settings["seed"]}.
A change counts only when its interval excludes zero and it survives the false discovery rate
correction across all metrics (q = {settings.get("fdr_q", 0.05)}). Changes smaller than a metric's minimum effect are marked negligible.</div></div>
<h2>Metrics</h2>
<div class="card"><table><thead><tr><th>Metric</th><th>Base</th><th>Derivative</th>
<th>Delta</th><th>95% CI</th><th>p</th><th>Verdict</th></tr></thead><tbody>{"".join(metric_rows)}</tbody></table></div>
<h2>Comparability</h2>
<div class="card"><ul>{issue_rows}</ul>
<div class="muted">Prompt template: {e(str(settings.get("template_mode", "own")))}</div></div>
<h2>Weights</h2>
<div class="card">{weights_html}</div>
<h2>Proof</h2>
<div class="card"><table>{proof_rows}</table>
<div class="muted">Check this report with <code>modeldiffr verify report.json</code>.</div></div>
<h2>Models</h2>
<div class="grid">{_model_card("Base", result["base"])}{_model_card("Derivative", result["derivative"])}</div>
<h2>Plan</h2>
<div class="card"><table><thead><tr><th>Task</th><th>Items</th><th>Detectable change at 80% power</th></tr></thead>
<tbody>{plan_rows}</tbody></table></div>
<h2>Item details</h2>
<div class="card">{"".join(detail_blocks)}</div>
<h2>Notes</h2><div class="card"><ul>{notes}</ul>
<div class="muted">modeldiffr {e(result["modeldiffr_version"])} &middot; schema {e(result["schema_version"])}
 &middot; wall time {result["wall_time_seconds"]}s &middot; python {e(result["environment"]["python"])}</div></div>
</main></body></html>
"""


def write_reports(result: dict, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "report.json"
    html_path = out / "report.html"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(render_html(result), encoding="utf-8")
    return json_path, html_path
