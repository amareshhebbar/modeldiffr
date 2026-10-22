(function () {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const day = (iso) => new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

  async function load() {
    const res = await fetch("registry.json", { cache: "no-cache" });
    if (!res.ok) throw new Error("registry.json could not be loaded (" + res.status + ")");
    return res.json();
  }

  function verdictCell(v) {
    if (!v.any_change) return '<span class="verdict">No significant change</span>';
    const chips = v.changed.map((n) => '<span class="chip">' + esc(n) + "</span>").join("");
    return '<span class="verdict changed">' + v.changed.length + " changed</span><div class=\"chips\">" + chips + "</div>";
  }

  function marks(a) {
    return '<div class="marks"><span class="mark on">Hashes</span>' +
      '<span class="mark' + (a.signed ? " on" : "") + '">' + (a.signed ? "Signed" : "Unsigned") + "</span>" +
      (a.anchored ? '<span class="mark on">Timestamped</span>' : "") + "</div>";
  }

  function index() {
    let all = [];
    let filter = "all";
    const draw = () => {
      const q = $("#q").value.trim().toLowerCase();
      const rows = all.filter((a) => {
        if (filter === "changed" && !a.verdict.any_change) return false;
        if (filter === "same" && a.verdict.any_change) return false;
        if (!q) return true;
        const hay = [a.base, a.derivative, a.suite, a.audit_id].concat(a.metrics.map((m) => m.name)).join(" ").toLowerCase();
        return hay.includes(q);
      });
      $("#rows").innerHTML = rows.length ? rows.map((a) =>
        '<tr data-id="' + esc(a.id) + '">' +
        '<td><div class="pair"><a class="d" href="audit.html?id=' + esc(a.id) + '">' + esc(a.derivative) + '</a><span class="b">' + esc(a.base) + "</span></div></td>" +
        "<td>" + verdictCell(a.verdict) + "</td>" +
        "<td>" + esc(a.suite) + (a.items ? '<div class="when">' + a.items.toLocaleString() + " items</div>" : "") + "</td>" +
        "<td>" + marks(a) + "</td>" +
        '<td class="when">' + esc(day(a.created_at)) + "</td></tr>").join("")
        : '<tr><td colspan="5" class="empty">No audits match this filter. Clear the search to see all of them.</td></tr>';
    };
    load().then((reg) => {
      all = reg.audits;
      const changed = all.filter((a) => a.verdict.any_change).length;
      const signed = all.filter((a) => a.signed).length;
      $("#tally").innerHTML =
        "<li><strong>" + all.length + "</strong><span>audits</span></li>" +
        "<li><strong>" + changed + "</strong><span>with a significant change</span></li>" +
        "<li><strong>" + signed + "</strong><span>signed</span></li>";
      $("#foot").textContent = "Generated " + day(reg.generated_at) + " by " + reg.generator + ".";
      draw();
    }).catch((e) => {
      $("#rows").innerHTML = '<tr><td colspan="5" class="empty">' + esc(e.message) + ". Serve this folder over HTTP, for example with python -m http.server.</td></tr>";
    });
    $("#q").addEventListener("input", draw);
    document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
      filter = b.dataset.f;
      document.querySelectorAll(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      draw();
    }));
    $("#rows").addEventListener("click", (ev) => {
      const tr = ev.target.closest("tr[data-id]");
      if (tr && !ev.target.closest("a")) location.href = "audit.html?id=" + encodeURIComponent(tr.dataset.id);
    });
  }

  function tone(m) {
    if (!m.significant || m.negligible) return "flat";
    if (m.directional === false || m.higher_is_better === null || m.higher_is_better === undefined) return "moved";
    return (m.delta > 0) === m.higher_is_better ? "better" : "worse";
  }

  function forest(metrics, avail) {
    const fmt = (x) => (x > 0 ? "+" : "") + x.toFixed(3);
    const width = Math.max(300, Math.round(avail || 720));
    const stacked = width < 560;
    const row = stacked ? 48 : 34;
    const top = 26;
    const left = stacked ? 8 : 190;
    const right = stacked ? 64 : 120;
    const plot = width - left - right;
    let lo = Math.min(0, ...metrics.map((m) => m.ci_low));
    let hi = Math.max(0, ...metrics.map((m) => m.ci_high));
    const pad = (hi - lo) * 0.08 || 0.01;
    lo -= pad; hi += pad;
    const x = (v) => left + ((v - lo) / (hi - lo)) * plot;
    const h = top + metrics.length * row + 8;
    const ticks = [lo, (lo + hi) / 2, hi].map((t, i) =>
      '<line class="gridline" x1="' + x(t) + '" x2="' + x(t) + '" y1="' + (top - 8) + '" y2="' + (h - 4) + '"/>' +
      '<text class="num" x="' + x(t) + '" y="14" text-anchor="' + (i === 0 ? "start" : i === 2 ? "end" : "middle") + '">' + fmt(t) + "</text>").join("");
    const rows = metrics.map((m, i) => {
      const y = top + i * row + (stacked ? row - 14 : row / 2);
      const ty = stacked ? y - 14 : y + 4;
      const t = tone(m);
      const label = !stacked && m.name.length > 26 ? m.name.slice(0, 25) + "\u2026" : m.name;
      return '<g><title>' + esc(m.name) + ": " + fmt(m.delta) + " [" + fmt(m.ci_low) + ", " + fmt(m.ci_high) + "]</title>" +
        '<text class="name" x="' + (stacked ? left : 0) + '" y="' + ty + '">' + esc(label) + "</text>" +
        '<line class="ci ' + t + '" x1="' + x(m.ci_low) + '" x2="' + x(m.ci_high) + '" y1="' + y + '" y2="' + y + '"/>' +
        '<circle class="' + t + '" cx="' + x(m.delta) + '" cy="' + y + '" r="4.5"/>' +
        '<text class="num" x="' + (width - 4) + '" y="' + (y + 4) + '" text-anchor="end">' + fmt(m.delta) + "</text></g>";
    }).join("");
    return '<svg class="forest" width="' + width + '" height="' + h + '" viewBox="0 0 ' + width + " " + h + '" role="img" aria-label="Change per metric with 95 percent intervals">' +
      ticks + '<line class="zero" x1="' + x(0) + '" x2="' + x(0) + '" y1="' + (top - 8) + '" y2="' + (h - 4) + '"/>' + rows + "</svg>";
  }

  function fact(k, v) {
    return "<dt>" + esc(k) + "</dt><dd>" + v + "</dd>";
  }

  function renderChecks(list) {
    $("#checks").innerHTML = list.map((c) =>
      '<li class="' + esc(c.status) + '"><span class="s">' + esc(c.status.toUpperCase()) + '</span><span><span class="n">' + esc(c.name) + '</span><br><span class="dt">' + esc(c.detail) + "</span></span></li>").join("");
  }

  async function audit() {
    const id = new URLSearchParams(location.search).get("id") || "";
    let reg;
    try {
      reg = await load();
    } catch (e) {
      $("#title").textContent = e.message;
      return;
    }
    const a = reg.audits.find((x) => x.id === id);
    if (!a) {
      $("#title").textContent = "No audit with id " + id;
      $("#status").textContent = "Go back to the list and pick an audit.";
      return;
    }
    document.title = a.derivative + " | " + reg.title;
    $("#title").textContent = a.derivative;
    $("#from").innerHTML = "compared with <b>" + esc(a.base) + "</b> on the " + esc(a.suite) + " suite, " + esc(day(a.created_at));
    const drawForest = () => { $("#forest").innerHTML = forest(a.metrics, $("#forest").clientWidth); };
    drawForest();
    let resizeTimer;
    window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawForest, 120); });
    const dir = "audits/" + a.id + "/";
    if (a.features) {
      const c = a.features.classes;
      $("#featsec").hidden = false;
      $("#feats").innerHTML = '<ul class="tally"><li><strong>' + c.derivative_only + "</strong><span>new features</span></li><li><strong>" +
        c.base_only + "</strong><span>lost</span></li><li><strong>" + c.shifted + "</strong><span>shifted</span></li></ul>" +
        '<p>Crosscoder at layer ' + a.features.layer + '. <a href="' + dir + 'features.html">Open the feature report</a> to read examples for each feature.</p>';
    }
    $("#facts").innerHTML =
      fact("Audit id", '<span class="hash">' + esc(a.audit_id) + "</span>") +
      fact("Base", esc(a.base) + (a.base_root ? '<br><span class="hash">' + esc(a.base_root) + "</span>" : "")) +
      fact("Derivative", esc(a.derivative) + (a.derivative_root ? '<br><span class="hash">' + esc(a.derivative_root) + "</span>" : "")) +
      fact("Suite", esc(a.suite) + (a.items ? ", " + a.items.toLocaleString() + " items" : "")) +
      fact("Changed", a.verdict.changed.length ? a.verdict.changed.map((n) => '<span class="chip">' + esc(n) + "</span>").join(" ") : "Nothing outside noise") +
      fact("Tool", esc("modeldiffr " + (a.modeldiffr_version || "")));
    $("#files").innerHTML = a.files.map((f) => '<li><a href="' + dir + esc(f) + '">' + esc(f) + "</a></li>").join("");
    const keyArg = reg.keys.length === 1 ? " --key " + reg.keys[0].name + ".pub" : "";
    $("#cmd").textContent = "pip install modeldiffr[proof]\ncurl -O " + new URL(dir + "report.json", location.href).href +
      (a.files.includes("report.dsse.json") ? "\ncurl -O " + new URL(dir + "report.dsse.json", location.href).href : "") +
      "\nmodeldiffr verify report.json" + keyArg;
    const results = [];
    renderChecks([{ name: "report.json", status: "wait", detail: "downloading" }]);
    try {
      const report = await (await fetch(dir + "report.json")).json();
      const r = ModeldiffrVerify.verifyReport(report);
      results.push(...r.checks);
      renderChecks(results);
      if (a.files.includes("report.dsse.json")) {
        const env = await (await fetch(dir + "report.dsse.json")).json();
        results.push(reg.keys.length ? await ModeldiffrVerify.verifyEnvelope(env, report, reg.keys)
          : { name: "signature", status: "skip", detail: "no publisher keys are listed in this registry" });
      }
      if (a.files.includes("report.sigstore.json")) {
        results.push({ name: "sigstore", status: "skip", detail: "Sigstore bundles are checked with modeldiffr verify --identity --issuer" });
      }
      renderChecks(results);
      const failed = results.filter((c) => c.status === "fail").length;
      $("#status").className = "status " + (failed ? "bad" : "ok");
      $("#status").textContent = failed ? failed + " check" + (failed > 1 ? "s" : "") + " failed. Do not rely on this audit." : "Every hash matches the report.";
    } catch (e) {
      $("#status").className = "status bad";
      $("#status").textContent = "Could not check the report: " + e.message;
    }
    $("#foot").textContent = "Generated " + day(reg.generated_at) + " by " + reg.generator + ".";
  }

  window.ModeldiffrRegistry = { index, audit, forest };
})();
