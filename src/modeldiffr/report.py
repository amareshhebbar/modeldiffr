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
    cap = result["items"]["capability"]
    cap_rows = "".join(
        f"<tr><td>{e(b['question'])}</td><td>{e(b['expected'])}</td>"
        f"<td>{e(b['predicted'])}</td><td>{e(d['predicted'])}</td></tr>"
        for b, d in zip(cap["base"], cap["derivative"], strict=True)
    )
    ref = result["items"]["over_refusal"]
    ref_rows = "".join(
        f"<tr><td>{e(b['prompt'])}</td><td>{'refused' if b['refused'] else 'answered'}</td>"
        f"<td>{'refused' if d['refused'] else 'answered'}</td></tr>"
        for b, d in zip(ref["base"], ref["derivative"], strict=True)
    )
    settings = result["settings"]
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
A change counts only when its interval excludes zero.</div></div>
<h2>Metrics</h2>
<div class="card"><table><thead><tr><th>Metric</th><th>Base</th><th>Derivative</th>
<th>Delta</th><th>95% CI</th><th>Verdict</th></tr></thead><tbody>{"".join(metric_rows)}</tbody></table></div>
<h2>Models</h2>
<div class="grid">{_model_card("Base", result["base"])}{_model_card("Derivative", result["derivative"])}</div>
<h2>Item details</h2>
<div class="card"><details><summary>Capability items ({len(cap["base"])})</summary>
<table><thead><tr><th>Question</th><th>Expected</th><th>Base</th><th>Derivative</th></tr></thead>
<tbody>{cap_rows}</tbody></table></details>
<details><summary>Over refusal prompts ({len(ref["base"])})</summary>
<table><thead><tr><th>Prompt</th><th>Base</th><th>Derivative</th></tr></thead>
<tbody>{ref_rows}</tbody></table></details></div>
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
