import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const GRAPH = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");   // viewer/graph

/* The shipped files: every .js/.css/.html under viewer/graph/ whose path has no test/ segment (the builder's rule). */
function shipped(dir = GRAPH, out = []) {
  for (const n of readdirSync(dir).sort()) {
    const p = path.join(dir, n);
    if (statSync(p).isDirectory()) { if (n !== "test") shipped(p, out); }
    else out.push(p);
  }
  return out;
}
const files = shipped();
const rel = (p) => path.relative(GRAPH, p);
const read = (p) => readFileSync(p, "utf8");

test("the shipped set is the expected one (generated, not listed), and nothing from test/ is in it", () => {
  const names = files.map(rel);
  for (const must of ["graph.css", "shell.html", "page/app.js", "page/dom.js", "page/data.js", "page/face.js", "page/sheet.js", "engine/index.js"])
    assert.ok(names.includes(must), must);
  assert.ok(names.every((n) => !n.split(path.sep).includes("test")));
});

/* The spec's full sink list (section 4, R7 GREP GATE). The engine branch's tools/graph_js_check.py carries a subset; this
   test is the whole list, applied to the page layer AND the engine. */
const SINKS = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser", "createContextualFragment", "setHTMLUnsafe",
  "parseHTMLUnsafe", "srcdoc", "eval(", "new Function", "Function(", "Worker(", "importScripts", "import(", "createElementNS", "http:", "https:"];
for (const f of files) {
  test("no sink, no URL literal: " + rel(f), () => {
    const src = read(f);
    for (const s of SINKS) assert.ok(!src.includes(s), rel(f) + " contains " + s);
    assert.ok(!/set(Timeout|Interval)\s*\(\s*["'`]/.test(src), "a string timer");
  });
}

test("R1: only dom.js creates elements; page code adds text only as text nodes", () => {
  for (const f of files.filter((x) => x.includes(path.join("graph", "page")) && x.endsWith(".js"))) {
    const n = rel(f), src = read(f);
    if (n !== path.join("page", "dom.js")) {
      assert.ok(!/createElement\s*\(/.test(src), n + " creates an element outside el()");
      assert.ok(!/\.(textContent|innerText)\s*=[^=]/.test(src), n + " assigns text without createTextNode");
      assert.ok(!/setAttribute\s*\(\s*["']on/i.test(src), n);
      assert.ok(!/\.style\.cssText|\.setAttribute\(\s*["']style/.test(src), n);
    }
  }
});

test("BOUNDARY: the engine imports nothing of the page; the page imports the engine only through ../engine/index.js", () => {
  for (const f of files.filter((x) => x.includes(path.join("graph", "engine")) && x.endsWith(".js"))) {
    const src = read(f);
    assert.ok(!/from\s+["'][^"']*page\//.test(src), rel(f));
  }
  const app = read(path.join(GRAPH, "page", "app.js"));
  const eng = [...app.matchAll(/from\s+"(\.\.\/engine\/[^"]*)"/g)].map((m) => m[1]);
  assert.deepEqual(eng, ["../engine/index.js"]);
  for (const f of files.filter((x) => x.includes(path.join("graph", "page")) && x.endsWith(".js") && !x.endsWith("app.js")))
    assert.ok(!read(f).includes("/engine/"), rel(f));
});

test("the shell: R6 and the contract's section 1 item 1", () => {
  const sh = read(path.join(GRAPH, "shell.html"));
  assert.equal(sh.split("{{CARDS}}").length - 1, 1, "exactly one {{CARDS}}");
  assert.equal((sh.match(/<script\b/gi) || []).length, 1, "exactly one script tag");
  assert.match(sh, /<script type="module" src="page\/app\.js"><\/script>/);
  assert.equal((sh.match(/<link\b/gi) || []).length, 2, "the two stylesheet links (checked in order below)");
  assert.match(sh, /<link rel="stylesheet" href="graph\.css">/);
  assert.match(sh, /<meta name="viewport" content="width=device-width, initial-scale=1">/);
  assert.match(sh, /^<!doctype html>/i);
  assert.match(sh, /<meta charset="utf-8">/i);
  assert.ok(!/<style/i.test(sh) && !/\sstyle\s*=/i.test(sh), "no style block or attribute");
  assert.ok(!/<[^>]*\son[a-z]+\s*=/i.test(sh), "no on... attribute");
  assert.ok(!/https?:/.test(sh));
  // every {{S:key}} sits in a TEXT position: between a '>' and a '<', never inside a tag
  const stripped = sh.replace(/\{\{S:[a-z_]+\}\}/g, "");
  assert.ok(!/<[^>]*\{\{/.test(sh), "a token inside a tag");
  assert.ok(sh.includes("{{S:") && !stripped.includes("{{S:"));
  // no reader-facing word sits in the shell outside a token: strip tags and tokens, nothing but whitespace and the card token is left
  const text = sh.replace(/<head>[\s\S]*?<\/head>/i, "").replace(/<[^>]*>/g, "").replace(/\{\{S:[a-z_]+\}\}/g, "").replace("{{CARDS}}", "").replace(/<!doctype html>/i, "").trim();
  assert.equal(text, "", "the shell has a literal word: " + JSON.stringify(text.slice(0, 80)));
});

test("CSS: no remote font or asset, no minimap, system font stacks only", () => {
  const css = read(path.join(GRAPH, "graph.css"));
  assert.ok(!/url\s*\(/i.test(css) && !/@font-face/i.test(css));
  assert.ok(!/[.#]mini\b|canvas/i.test(css), "no minimap rule");
  assert.ok(!/Source Serif|Inter\b|JetBrains/.test(css));
  assert.match(css, /\.graph-sheet\.comments-editing/);
  assert.match(css, /\.graph-sheet-body/);
});

test("stylesheets: the shell links engine.css then graph.css, in that order, and no shipped CSS imports or uses url()", () => {
  const sh = read(path.join(GRAPH, "shell.html"));
  const links = [...sh.matchAll(/<link\b[^>]*>/gi)].map((m) => m[0]);
  assert.deepEqual(links, ['<link rel="stylesheet" href="engine/engine.css">', '<link rel="stylesheet" href="graph.css">']);
  for (const f of files.filter((x) => x.endsWith(".css"))) {
    const css = read(f);
    assert.ok(!/@import/i.test(css), rel(f) + " has an @import");
    assert.ok(!/url\s*\(/i.test(css), rel(f) + " uses url()");
  }
});

/* ---- Scans of the page layer's own code (engine and tests excluded) -------------------------------------------------- */
const pageFiles = files.filter((x) => x.includes(path.join("graph", "page")) && x.endsWith(".js"));

/* The text of the call whose "(" is at `open`: up to the matching ")", skipping string literals. */
function callText(src, open) {
  let depth = 0, q = null;
  for (let i = open; i < src.length; i++) {
    const c = src[i];
    if (q) { if (c === "\\") i++; else if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === "`") { q = c; continue; }
    if (c === "(") depth++;
    else if (c === ")" && --depth === 0) return src.slice(open, i + 1);
  }
  return src.slice(open);
}

/* Every call of `name(` (`.method(` or a bare call; a `function name(` definition is not a call): [{at, text}]. */
function callsOf(src, name) {
  const out = [];
  const pat = name.startsWith(".") ? "\\" + name : "(?<![\\w$.])" + name;
  const re = new RegExp("(?<!function\\s)" + pat + "\\(", "g");
  for (const m of src.matchAll(re)) out.push({ at: m.index, text: callText(src, m.index + m[0].length - 1) });
  return out;
}

/* The name of the innermost `function NAME(...) {` that contains index `at` (null at top level). */
function enclosingFunction(src, at) {
  let best = null;
  for (const m of src.matchAll(/function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{/g)) {
    let depth = 0, end = -1;
    for (let i = m.index + m[0].length - 1; i < src.length; i++) {
      if (src[i] === "{") depth++;
      else if (src[i] === "}" && --depth === 0) { end = i; break; }
    }
    if (m.index < at && at < end && (!best || m.index > best.start)) best = { name: m[1], start: m.index };
  }
  return best ? best.name : null;
}

/* B1: every listener the page adds is removed by the one teardown, because each passes the shared signal. */
function listenersWithoutSignal(src) {
  return callsOf(src, ".addEventListener").filter((c) => !/\bsignal\b/.test(c.text.slice(c.text.lastIndexOf(",") + 1))).map((c) => c.text.slice(0, 60));
}
/* B1: every engine subscription is kept as an unsubscribe function, so the teardown can remove it. */
function subscriptionsNotKept(src) {
  return callsOf(src, ".on").filter((c) => !/offs\.push\(\s*[\w.]*$/.test(src.slice(Math.max(0, c.at - 60), c.at))).map((c) => c.text.slice(0, 40));
}

test("B1: every addEventListener in page code passes the shared signal; every engine subscription is kept for teardown", () => {
  let seen = 0;
  for (const f of pageFiles) {
    const src = read(f);
    seen += callsOf(src, ".addEventListener").length;
    assert.deepEqual(listenersWithoutSignal(src), [], rel(f) + " has a listener without the shared signal");
    assert.deepEqual(subscriptionsNotKept(src), [], rel(f) + " has an engine subscription that teardown cannot remove");
  }
  assert.ok(seen >= 10, "the scan found the listeners it is meant to police: " + seen);
});

test("B1 scan control: a planted listener without the signal, and a planted subscription not kept, are found", () => {
  assert.equal(listenersWithoutSignal('x.addEventListener("click", () => f(1, 2));').length, 1);
  assert.equal(listenersWithoutSignal('x.addEventListener("click", () => f(1, 2), { signal });').length, 0);
  assert.equal(listenersWithoutSignal('x.addEventListener("click", () => f(), { once: true });').length, 1);
  assert.equal(subscriptionsNotKept('handle.on("tap", fn);').length, 1);
  assert.equal(subscriptionsNotKept("offs.push(handle.on(\"tap\", fn));").length, 0);
});

/* S4: the sheet's content moves in one place (adopt, only after close()) and ends in one place (release, only from
   close() and dispose()); the page ends it only through sheet.close() or, at the fallback, sheet.dispose(). */
function closeRouteViolations(name, src) {
  const bad = [];
  const where = (c) => name + " " + c.text.slice(0, 50);
  if (name === "sheet.js") {
    for (const c of callsOf(src, "release")) if (!["close", "dispose"].includes(enclosingFunction(src, c.at))) bad.push(where(c) + " (release outside close/dispose)");
    for (const c of callsOf(src, "adopt")) if (!["showCard", "showPanel"].includes(enclosingFunction(src, c.at))) bad.push(where(c) + " (adopt outside showCard/showPanel)");
    for (const m of ["appendChild", "insertBefore", "removeChild", "replaceChild"]) {
      for (const c of callsOf(src, "." + m)) {
        if (/\b(rec\.)?node\b/.test(c.text) && !["release", "adopt", "clear"].includes(enclosingFunction(src, c.at))) bad.push(where(c) + " (moves the root outside release/adopt)");
      }
    }
    // clear(node) empties a container it is handed; handed the sheet body it would take the root out
    for (const c of callsOf(src, "clear")) if (/^\(\s*body\b/.test(c.text)) bad.push(where(c) + " (clears the body, which holds the root)");
    for (const fn of ["showCard", "showPanel"]) {
      const m = src.match(new RegExp("function " + fn + "\\([^)]*\\)\\s*\\{\\s*\\n\\s*if \\(!close\\(\\)\\) return false;"));
      if (!m) bad.push(name + " " + fn + " does not begin with the one close function");
    }
  } else {
    for (const c of callsOf(src, "release")) bad.push(where(c) + " (the page calls release)");
    for (const c of callsOf(src, "adopt")) bad.push(where(c) + " (the page calls adopt)");
    for (const c of callsOf(src, ".dispose")) if (enclosingFunction(src, c.at) !== "fallback") bad.push(where(c) + " (dispose outside the fallback)");
    for (const m of ["appendChild", "insertBefore", "removeChild", "replaceChild"])
      for (const c of callsOf(src, "." + m)) if (enclosingFunction(src, c.at) !== "fallback") bad.push(where(c) + " (the page moves a node outside the fallback)");
  }
  return bad;
}

test("S4: the sheet is ended and its root moved only through close() and the fallback teardown", () => {
  let checked = 0;
  for (const f of pageFiles) {
    const n = path.basename(f);
    if (n !== "sheet.js" && n !== "app.js") continue;
    assert.deepEqual(closeRouteViolations(n, read(f)), [], n);
    checked++;
  }
  assert.equal(checked, 2);
});

test("S4 scan control: planted calls are found", () => {
  const app = read(path.join(GRAPH, "page", "app.js")), sheet = read(path.join(GRAPH, "page", "sheet.js"));
  assert.equal(closeRouteViolations("app.js", app + '\nroutes["x"] = () => sheet.dispose();\n').length, 1);
  assert.equal(closeRouteViolations("app.js", app + "\nfunction other() { release(1); }\n").length, 1);
  assert.equal(closeRouteViolations("sheet.js", sheet + "\nfunction extra() { release(cur); }\n").length, 1);
  assert.equal(closeRouteViolations("sheet.js", sheet + "\nfunction extra2() { body.appendChild(node); }\n").length, 1);
  assert.equal(closeRouteViolations("sheet.js", sheet + "\nfunction extra3() { adopt(node, true); }\n").length, 1);
  assert.equal(closeRouteViolations("sheet.js", sheet.replace("if (!close()) return false;\n    const rec", "const rec")).length, 1);
});
