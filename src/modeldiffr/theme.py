FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wdth,wght@75..100,400..700'
    '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
)

CSS = """
:root{--paper:#f6f7f4;--sheet:#fff;--ink:#18202b;--muted:#5b6573;--rule:#dce0da;--grid:#eceee8;
--base:#2d5bd7;--deriv:#b86e00;--worse:#b42318;--better:#087443;
--sans:"Instrument Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
--mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--paper:#0f141a;--sheet:#151b23;--ink:#e7eaee;--muted:#97a1ae;
--rule:#273039;--grid:#1b222b;--base:#7c9cff;--deriv:#f0a830;--worse:#ff8a7a;--better:#5fd49a}}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:400 16px/1.55 var(--sans)}
main{max-width:1080px;margin:0 auto;padding:40px 16px 64px}
h1{font-size:clamp(26px,4vw,38px);line-height:1.1;letter-spacing:-.03em;font-weight:600;font-stretch:88%;margin:0 0 8px;word-break:break-word}
h2{font-size:17px;font-weight:600;margin:0 0 14px;letter-spacing:-.01em}
h3{font-size:15px;font-weight:600;margin:0 0 8px}
p{max-width:72ch}.muted{color:var(--muted)}
.lede{color:var(--muted);font-size:17px;margin:0 0 28px}
.lede b{color:var(--base);font-weight:500}.lede i{color:var(--deriv);font-style:normal;font-weight:500}
.sheet{background:var(--sheet);border:1px solid var(--rule);border-radius:8px;padding:20px;margin-bottom:20px;overflow-x:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--grid);vertical-align:top}
th{font-weight:500;color:var(--muted);font-size:13px;border-bottom-color:var(--rule)}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap;font-family:var(--mono);font-size:13px}
code,.hash{font-family:var(--mono);font-size:.86em}.hash{word-break:break-all;color:var(--muted)}
.tag{display:inline-flex;align-items:center;gap:6px;font-size:13px;font-weight:500;white-space:nowrap}
.tag::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--muted)}
.tag.worse::before{background:var(--worse)}.tag.better::before{background:var(--better)}
.tag.moved::before{background:var(--deriv)}h2 .tag{font-size:inherit;font-weight:600}.tag.base::before{background:var(--base)}
.tally{display:flex;flex-wrap:wrap;gap:28px;list-style:none;padding:0;margin:0 0 24px}
.tally li{display:flex;flex-direction:column}.tally strong{font-size:28px;font-weight:600;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.tally span{color:var(--muted);font-size:14px}
.ex{font-family:var(--mono);font-size:12.5px;line-height:1.5;color:var(--muted);white-space:pre-wrap;word-break:break-word;margin:2px 0}
.ex mark{background:color-mix(in srgb,var(--deriv) 25%,transparent);color:var(--ink);border-radius:2px;padding:0 1px}
details{border-top:1px solid var(--grid);padding:10px 0}details summary{cursor:pointer}
footer{color:var(--muted);font-size:13px;margin-top:32px}
.bars{display:flex;align-items:flex-end;gap:3px;height:120px;margin:8px 0 4px}
.bars span{flex:1;background:var(--muted);border-radius:2px 2px 0 0;min-height:1px}
.bars span.lo{background:var(--base)}.bars span.hi{background:var(--deriv)}
.axis{display:flex;justify-content:space-between;font-size:12px;color:var(--muted)}
"""


def page(title: str, body: str) -> str:
    import html

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title>{FONTS}<style>{CSS}</style></head>"
        f"<body><main>{body}</main></body></html>"
    )
