(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ModeldiffrVerify = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]);

  function sha256(bytes) {
    const n = bytes.length;
    const total = Math.ceil((n + 9) / 64) * 64;
    const buf = new Uint8Array(total);
    buf.set(bytes);
    buf[n] = 0x80;
    const view = new DataView(buf.buffer);
    view.setUint32(total - 8, Math.floor((n * 8) / 0x100000000));
    view.setUint32(total - 4, (n * 8) >>> 0);
    const h = new Uint32Array([
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ]);
    const w = new Uint32Array(64);
    for (let off = 0; off < total; off += 64) {
      for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + i * 4);
      for (let i = 16; i < 64; i++) {
        const a = w[i - 15], b = w[i - 2];
        const s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3);
        const s1 = ((b >>> 17) | (b << 15)) ^ ((b >>> 19) | (b << 13)) ^ (b >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
      }
      let [a, b, c, d, e, f, g, hh] = h;
      for (let i = 0; i < 64; i++) {
        const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        const ch = (e & f) ^ (~e & g);
        const t1 = (hh + S1 + ch + K[i] + w[i]) >>> 0;
        const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + maj) >>> 0;
        hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0; h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0;
      h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0; h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + hh) >>> 0;
    }
    const out = new Uint8Array(32);
    const ov = new DataView(out.buffer);
    for (let i = 0; i < 8; i++) ov.setUint32(i * 4, h[i]);
    return out;
  }

  const enc = new TextEncoder();
  const utf8 = (s) => enc.encode(s);
  const hex = (b) => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  const fromHex = (s) => new Uint8Array(s.match(/../g).map((x) => parseInt(x, 16)));
  const concat = (...parts) => {
    const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
    let o = 0;
    for (const p of parts) { out.set(p, o); o += p.length; }
    return out;
  };

  function canonical(value) {
    if (value === null) return "null";
    if (value === true) return "true";
    if (value === false) return "false";
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw new Error("NaN and infinity cannot be serialized");
      return Object.is(value, -0) ? "0" : String(value);
    }
    if (typeof value === "string") return JSON.stringify(value);
    if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
    if (typeof value === "object") {
      const keys = Object.keys(value).sort();
      return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
    }
    throw new Error("cannot serialize " + typeof value);
  }

  const LEAF = new Uint8Array([0]);
  const NODE = new Uint8Array([1]);
  const leafHash = (data) => sha256(concat(LEAF, data));
  const nodeHash = (l, r) => sha256(concat(NODE, l, r));

  function merkleRoot(leaves) {
    if (!leaves.length) return sha256(new Uint8Array(0));
    const rec = (lo, hi) => {
      const n = hi - lo;
      if (n === 1) return leaves[lo];
      let k = 1;
      while (k * 2 < n) k *= 2;
      return nodeHash(rec(lo, lo + k), rec(lo + k, hi));
    };
    return rec(0, leaves.length);
  }

  const objectHash = (v) => "sha256:" + hex(sha256(utf8(canonical(v))));
  const auditId = (manifest) => "mdr1:" + hex(sha256(utf8(canonical(manifest))));

  function resultsRoot(items) {
    const leaves = [];
    for (const task of Object.keys(items).sort()) {
      const block = items[task];
      for (const side of ["base", "derivative", "pair"]) {
        (block[side] || []).forEach((row, index) => {
          leaves.push(leafHash(utf8(canonical({ task, side, index, row }))));
        });
      }
    }
    return "sha256:" + hex(merkleRoot(leaves));
  }

  function weightsRoot(leaves) {
    const ordered = Object.keys(leaves).sort().map((k) => fromHex(leaves[k]));
    return "sha256:" + hex(merkleRoot(ordered));
  }

  function statementHash(r) {
    return objectHash({
      audit_id: r.audit_id,
      results_root: r.proof.results_root,
      metrics: r.metrics,
      verdict: r.verdict,
      comparability: r.comparability,
      weights_diff: r.weights_diff === undefined ? null : r.weights_diff,
    });
  }

  function modelEntry(meta, fp) {
    fp = fp || {};
    const tok = fp.tokenizer || {};
    const w = fp.weights || {};
    const get = (o, k) => (o[k] === undefined ? null : o[k]);
    return {
      model_id: get(meta, "model_id"),
      revision: get(meta, "revision"),
      commit: get(fp, "commit"),
      weights_root: get(w, "root"),
      weights_algorithm: get(w, "algorithm"),
      tokenizer_vocab: get(tok, "vocab"),
      tokenizer_json: get(tok, "tokenizer_json"),
      chat_template: get(tok, "chat_template"),
    };
  }

  function expectedVerdict(metrics) {
    const changed = metrics.filter((m) => m.significant && !m.negligible).map((m) => m.name);
    const negligible = metrics.filter((m) => m.negligible).map((m) => m.name);
    return { changed, negligible, any_change: changed.length > 0 };
  }

  const check = (name, status, detail) => ({ name, status, detail });

  function verifyReport(r) {
    const checks = [];
    if (!r || !r.manifest || !r.proof || !r.items || !r.metrics) {
      return { ok: false, checks: [check("schema", "fail", "this is not a Modeldiffr report")] };
    }
    if (r.schema_version === "0.2") {
      return {
        ok: true,
        checks: [check("schema", "skip", "schema 0.2 reports are checked with modeldiffr verify")],
      };
    }
    const id = auditId(r.manifest);
    const idOk = id === r.audit_id && id === r.proof.audit_id;
    checks.push(check("audit_id", idOk ? "pass" : "fail", idOk ? id : "manifest hashes to " + id));
    let same = canonical(r.manifest.settings) === canonical(r.settings);
    for (const side of ["base", "derivative"]) {
      const fp = (r.fingerprints || {})[side];
      same = same && canonical(modelEntry(r[side], fp)) === canonical(r.manifest[side]);
    }
    checks.push(check("manifest_consistency", same ? "pass" : "fail",
      same ? "settings and fingerprints match the manifest" : "settings or fingerprints differ from the manifest"));
    const rr = resultsRoot(r.items);
    const rrOk = rr === r.proof.results_root;
    checks.push(check("results_root", rrOk ? "pass" : "fail", rrOk ? rr : "items were changed"));
    const v = expectedVerdict(r.metrics);
    const vOk = canonical(v) === canonical(r.verdict);
    checks.push(check("verdict", vOk ? "pass" : "fail", v.changed.join(", ") || "no change"));
    for (const side of ["base", "derivative"]) {
      const w = (((r.fingerprints || {})[side]) || {}).weights || {};
      if (!w.leaves) continue;
      const got = weightsRoot(w.leaves);
      checks.push(check(side + "_weights_leaves", got === w.root ? "pass" : "fail",
        got === w.root ? Object.keys(w.leaves).length + " tensors" : "tensor hashes do not give the root"));
    }
    const sh = statementHash(r);
    const shOk = sh === r.proof.statement_sha256;
    checks.push(check("statement", shOk ? "pass" : "fail", shOk ? "claims match the statement hash" : "statement hashes to " + sh));
    checks.push(check("metrics", "skip", "bootstrap intervals are recomputed by modeldiffr verify"));
    return { ok: checks.every((c) => c.status !== "fail"), checks };
  }

  function b64(s) {
    if (typeof atob === "function") return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
    return new Uint8Array(Buffer.from(s, "base64"));
  }

  function pemBody(pem) {
    return b64(pem.replace(/-----[^-]+-----/g, "").replace(/\s+/g, ""));
  }

  function pae(type, payload) {
    const t = utf8(type);
    return concat(utf8("DSSEv1 " + t.length + " "), t, utf8(" " + payload.length + " "), payload);
  }

  function binding(statement, r) {
    const problems = [];
    if (statement._type !== "https://in-toto.io/Statement/v1") problems.push("not an in toto v1 statement");
    if (statement.predicateType !== "https://modeldiffr.dev/attestation/audit/v1") problems.push("not a Modeldiffr audit attestation");
    const p = statement.predicate || {};
    if (p.audit_id !== r.audit_id) problems.push("signed audit_id does not match the report");
    if (p.results_root !== r.proof.results_root) problems.push("signed results_root does not match the report");
    if (p.statement_sha256 !== r.proof.statement_sha256) problems.push("signed statement_sha256 does not match the report");
    if (canonical(p.verdict || null) !== canonical(r.verdict)) problems.push("signed verdict does not match the report");
    return problems;
  }

  async function verifyEnvelope(env, report, keys) {
    const subtle = (typeof crypto !== "undefined" && crypto.subtle) || null;
    if (!subtle) return check("signature", "skip", "this browser has no Web Crypto");
    const payload = b64(env.payload);
    const message = pae(env.payloadType, payload);
    for (const k of keys || []) {
      const der = pemBody(k.pem);
      const raw = der.slice(der.length - 32);
      const kid = "ed25519:" + hex(sha256(raw)).slice(0, 32);
      for (const s of env.signatures || []) {
        if (s.keyid && s.keyid !== kid) continue;
        let key;
        try {
          key = await subtle.importKey("spki", der, { name: "Ed25519" }, false, ["verify"]);
        } catch (e) {
          return check("signature", "skip", "this browser cannot check Ed25519 signatures");
        }
        const ok = await subtle.verify({ name: "Ed25519" }, key, b64(s.sig), message);
        if (!ok) continue;
        const problems = binding(JSON.parse(new TextDecoder().decode(payload)), report);
        if (problems.length) return check("signature", "fail", problems.join("; "));
        return check("signature", "pass", "signed by " + k.name);
      }
    }
    return check("signature", "fail", "no listed publisher key verifies this signature");
  }

  return {
    sha256, hex, canonical, merkleRoot, leafHash, auditId, resultsRoot, weightsRoot,
    statementHash, modelEntry, expectedVerdict, verifyReport, verifyEnvelope, binding, pae,
  };
});
