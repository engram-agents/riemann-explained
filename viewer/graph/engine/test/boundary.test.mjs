// BOUNDARY: no engine file uses a forbidden SINK (HTML-string API, code evaluation, remote address, worker, ...) or a
// global, or imports from outside engine/; it names no page string, step id, address or card class. Tests are not engine files.
// The SINK list has ONE home: tools/graph_js_check.py. This file runs that gate on the engine folder and plants every token
// it once carried itself, so a token can never be in one list and not the other. What stays here is the engine-ONLY
// structural rules (the page legitimately uses window and document, the engine never does).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync, mkdtempSync, mkdirSync, writeFileSync, copyFileSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ENGINE = resolve(dirname(fileURLToPath(import.meta.url)), "..");
function files(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) return f === "test" ? [] : files(p);
    return [p];
  });
}
const FILES = files(ENGINE);
// Engine-only structural rule (NOT a sink list): the engine never touches the page, storage, the window or the network.
const GLOBALS = ["window", "globalThis", "document.", "localStorage", "sessionStorage", "fetch(", "XMLHttpRequest", "location.", "navigator."];
const PAGE_WORDS = [/riemann/i, /\bcard\b/i, /\.\.\/page/, /\brh-/, /\blean\b/i];
const src = (p) => readFileSync(p, "utf8");

test("the engine has files to scan (a scan over nothing proves nothing)", () => {
  const names = FILES.map((p) => relative(ENGINE, p)).sort();
  for (const must of ["INTERFACE.md", "index.js", "controller.js", "layout.js", "dom.js"]) assert.ok(names.includes(must), "missing " + must + " in " + names);
});
const GATE = resolve(ENGINE, "..", "..", "..", "tools", "graph_js_check.py");
function gate(dir) {
  const r = spawnSync("python3", ["-I", GATE, dir], { encoding: "utf8" });
  if (r.error) assert.fail("cannot run the grep gate: python3 is missing or failed to start (" + r.error.message + ")");
  return { rc: r.status, out: r.stdout + r.stderr };
}
function scratch(setup) {
  const d = mkdtempSync(join(tmpdir(), "boundary-"));
  try { return setup(d); } finally { rmSync(d, { recursive: true, force: true }); }
}
function copyEngine(dst) {
  for (const p of FILES) { const to = join(dst, relative(ENGINE, p)); mkdirSync(dirname(to), { recursive: true }); copyFileSync(p, to); }
}
test("the grep gate (the one sink list) passes on the engine folder", () => {
  const r = gate(ENGINE);
  assert.equal(r.rc, 0, r.out);
  assert.match(r.out, /, 0 refused,/, r.out);
});
test("the gate-backed check can fail: one planted token in a copy of the engine is refused", () => {
  scratch((d) => {
    copyEngine(d);
    writeFileSync(join(d, "layout.js"), src(join(ENGINE, "layout.js")) + "\nimportScripts(u);\n");
    const r = gate(d);
    assert.equal(r.rc, 1, r.out);
    assert.match(r.out, /REFUSED layout\.js:\d+ importScripts/, r.out);
  });
});
// Every token the old boundary lists carried as a sink, each planted ALONE: the gate must refuse each one (nothing lost in the move).
// A scheme counts in a string literal (the gate's deliberate rule: a bare `data:`-style key is code); a bare http: is not a sink.
const MOVED_SINKS = [
  ["innerHTML", "x.innerHTML = s;"], ["outerHTML", "x.outerHTML = s;"], ["insertAdjacentHTML", "x.insertAdjacentHTML('beforeend', s);"],
  ["document.write", "document.write(s);"], ["DOMParser", "new DOMParser();"], ["createContextualFragment", "r.createContextualFragment(s);"],
  ["eval(", "eval(s);"], ["new Function", "const f = new Function('return 1');"], ["createElementNS", "d.createElementNS(ns, 'g');"],
  ["http:", "const u = 'http://example.org/';"], ["https:", "const u = 'https://example.org/';"],
  ["<svg", "const s = '<svg></svg>';"], ["<canvas", "const c = '<canvas>';"],
  ["setHTMLUnsafe", "e.setHTMLUnsafe(s);"], ["parseHTMLUnsafe", "Document.parseHTMLUnsafe(s);"], ["srcdoc", "f.srcdoc = s;"],
  ["Worker(", "const w = new Worker(u);"], ["importScripts", "importScripts(u);"],
];
test("every token moved to the gate is refused by it when planted alone", () => {
  for (const [tok, line] of MOVED_SINKS) {
    scratch((d) => {
      writeFileSync(join(d, "a.js"), line + "\n");
      const r = gate(d);
      assert.equal(r.rc, 1, tok + " was not refused: " + r.out);
      assert.ok(r.out.includes("REFUSED a.js:1 " + tok), tok + " refused under another name: " + r.out);
    });
  }
});
test("a string setTimeout or setInterval is absent", () => {
  for (const p of FILES) assert.ok(!/set(Timeout|Interval)\s*\(\s*["'`]/.test(src(p)), relative(ENGINE, p));
});
function globalHits(t) { return GLOBALS.filter((tok) => t.includes(tok)); }
test("ENGINE-ONLY rule (not a sink list): no engine file touches a global, the document, storage or the network", () => {
  for (const p of FILES.filter((f) => f.endsWith(".js"))) { const hits = globalHits(src(p)); assert.deepEqual(hits, [], relative(ENGINE, p) + " contains " + hits); }
});
test("the engine-only global rule can fail: each global planted alone is seen", () => {
  for (const tok of GLOBALS) assert.deepEqual(globalHits("const x = " + tok + ";"), [tok]);
});
test("no engine file names a page word, an address or a card class", () => {
  for (const p of FILES) { const t = src(p); for (const re of PAGE_WORDS) assert.ok(!re.test(t), relative(ENGINE, p) + " matches " + re); }
});
test("every import stays inside engine/", () => {
  let n = 0;
  for (const p of FILES.filter((f) => f.endsWith(".js"))) {
    for (const m of src(p).matchAll(/(?:import|export)\s[^'"]*?from\s*["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']\s*\)|import\s+["']([^"']+)["']/g)) {
      const spec = m[1] ?? m[2] ?? m[3]; n++;
      assert.ok(spec.startsWith("./"), relative(ENGINE, p) + " imports " + spec + " (only ./ is allowed)");
      assert.ok(resolve(dirname(p), spec).startsWith(ENGINE + "/") && !relative(ENGINE, resolve(dirname(p), spec)).startsWith("test"), "outside engine/: " + spec);
    }
  }
  assert.ok(n > 5, "the import scan saw " + n + " imports");
});
test("elements are made in one place: createElement, createElementNS and setAttribute appear only in dom.js", () => {
  for (const p of FILES.filter((f) => f.endsWith(".js"))) {
    if (p.endsWith("/dom.js")) continue;
    const t = src(p);
    for (const tok of ["createElement", "createElementNS", "setAttribute", "setAttributeNS", "createTextNode", "textContent", "innerText"]) assert.ok(!t.includes(tok), relative(ENGINE, p) + " contains " + tok);
  }
  const d = src(join(ENGINE, "dom.js"));
  assert.ok(d.includes("createElement(") && d.includes("setAttribute") && !/svg|<path|createElementNS/i.test(d), "one tag table: div only");
  assert.ok(!d.includes("createTextNode") && !d.includes("textContent"), "the engine writes no text");
});
test("F4: no engine file reads an attribute or queries the DOM to identify a node (the element->node map is the only way)", () => {
  for (const p of FILES.filter((f) => f.endsWith(".js"))) {
    const t = src(p);
    for (const tok of ["getAttribute", ".closest(", "querySelector", ".matches(", "dataset"]) assert.ok(!t.includes(tok), relative(ENGINE, p) + " contains " + tok);
    if (!p.endsWith("/dom.js") && !p.endsWith("/view.js")) assert.ok(!t.includes("data-node"), relative(ENGINE, p) + " names data-node");
  }
});
