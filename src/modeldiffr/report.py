import html
import json
from pathlib import Path


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
    return f'<section class="sheet"><h2>{title}</h2><table>{rows}</table></section>'


def _forest(metrics: list[dict]) -> str:
    shown = [m for m in metrics if m.get("directional", True)]
    if not shown:
        return ""
    lo = min([0.0] + [m["ci_low"] for m in shown])
    hi = max([0.0] + [m["ci_high"] for m in shown])
    pad = (hi - lo) * 0.08 or 0.01
    lo, hi = lo - pad, hi + pad
    width, left, right, row, top = 720, 230, 80, 30, 24
    plot = width - left - right

    def x(v: float) -> float:
        return round(left + (v - lo) / (hi - lo) * plot, 1)

    height = top + row * len(shown) + 10
    parts = [
        f'<svg class="forest" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Change per metric with 95 percent intervals">',
        f'<line class="zero" x1="{x(0)}" x2="{x(0)}" y1="6" y2="{height - 4}"/>',
        f'<text class="num" x="{x(0)}" y="14" text-anchor="middle">0</text>',
    ]
    if x(0) - x(lo) > 70:
        parts.append(f'<text class="num" x="{x(lo)}" y="14">{lo:+.3f}</text>')
    if x(hi) - x(0) > 70:
        parts.append(f'<text class="num" x="{x(hi)}" y="14" text-anchor="end">{hi:+.3f}</text>')
    for i, m in enumerate(shown):
        y = top + i * row + row / 2
        tone, _ = _direction(m)
        parts.append(
            f"<g><title>{html.escape(m['name'])}: {m['delta']:+.4f} "
            f"[{m['ci_low']:+.4f}, {m['ci_high']:+.4f}]</title>"
            f'<text x="0" y="{y + 4}">{html.escape(m["name"])}</text>'
            f'<line class="ci {tone}" x1="{x(m["ci_low"])}" x2="{x(m["ci_high"])}" y1="{y}" y2="{y}"/>'
            f'<circle class="{tone}" cx="{x(m["delta"])}" cy="{y}" r="4.5"/>'
            f'<text class="num" x="{width}" y="{y + 4}" text-anchor="end">{m["delta"]:+.3f}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)


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
    from modeldiffr.theme import page

    changed_tag = "worse" if changed else "better"
    body = f"""
<h1>{e(result["derivative"]["model_id"])}</h1>
<p class="lede">compared with <b>{e(result["base"]["model_id"])}</b> on the {e(result["suite"]["name"])} suite, {e(result["created_at"])}</p>
<p><span class="tag {changed_tag}">{e(headline)}</span></p>
<section class="sheet"><h2>Change in each metric, derivative minus base</h2>
{_forest(result["metrics"])}
<p class="muted">95% bootstrap intervals from {settings["n_resamples"]} resamples, seed {settings["seed"]}. A change counts only when its interval excludes zero and it survives the false discovery rate correction across all metrics (q = {settings.get("fdr_q", 0.05)}). Changes smaller than a metric's minimum effect are marked negligible. Divergence metrics have no better or worse direction and are listed in the table only.</p></section>
<section class="sheet"><h2>Metrics</h2>
<table><thead><tr><th>Metric</th><th>Base</th><th>Derivative</th>
<th>Delta</th><th>95% CI</th><th>p</th><th>Verdict</th></tr></thead><tbody>{"".join(metric_rows)}</tbody></table></section>
<div class="grid">
<section class="sheet"><h2>Comparability</h2><ul>{issue_rows}</ul>
<p class="muted">Prompt template: {e(str(settings.get("template_mode", "own")))}</p></section>
<section class="sheet"><h2>Weights</h2>{weights_html}</section>
</div>
<section class="sheet"><h2>Proof</h2><table>{proof_rows}</table>
<p class="muted">Check this report with <code>modeldiffr verify report.json</code>, or against the real weights with <code>--models</code>.</p></section>
<div class="grid">{_model_card("Base", result["base"])}{_model_card("Derivative", result["derivative"])}</div>
<section class="sheet"><h2>Plan</h2><table><thead><tr><th>Task</th><th>Items</th><th>Detectable change at 80% power</th></tr></thead>
<tbody>{plan_rows}</tbody></table></section>
<section class="sheet"><h2>Item details</h2>{"".join(detail_blocks)}</section>
<section class="sheet"><h2>Notes</h2><ul>{notes}</ul></section>
<footer>modeldiffr {e(result["modeldiffr_version"])}, schema {e(result["schema_version"])}, wall time {result["wall_time_seconds"]}s, python {e(result["environment"]["python"])}.</footer>
"""
    return page(f"Audit: {result['derivative']['model_id']}", body)


def write_reports(result: dict, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "report.json"
    html_path = out / "report.html"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(render_html(result), encoding="utf-8")
    return json_path, html_path
