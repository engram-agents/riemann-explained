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


/* SECTION 8: the proof state comes from the data (`proof` and the symbols' words), never from the list page's own status line. */
function statusSelectors(code) {
  const src = code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");     // comments hold apostrophes
  const lits = [];
  for (let i = 0; i < src.length; i++) {          // the string literals, in order (a quote inside a literal is skipped)
    const q = src[i];
    if (q !== '"' && q !== "'" && q !== "`") continue;
    let j = i + 1;
    while (j < src.length && src[j] !== q) j += src[j] === "\\" ? 2 : 1;
    lits.push(src.slice(i + 1, j));
    i = j;
  }
  return lits.filter((l) => /(^|[\s>,+~(])[a-z]*\.status(?![\w-])/.test(l));
}

test("SECTION 8: no shipped page code selects `.status` or `p.status` (the page does not read the list's proof line)", () => {
  for (const f of pageFiles) assert.deepEqual(statusSelectors(read(f)), [], rel(f));
  assert.deepEqual(statusSelectors('art.querySelector(":scope > p.status.proof")'), [':scope > p.status.proof']);
  assert.deepEqual(statusSelectors("x.querySelector('.status')"), [".status"]);
  assert.deepEqual(statusSelectors('el("p", { class: "sheet-status" })'), []);
});


/* K2: no server- or exception-derived string reaches the DOM. The notice is a page constant: say() takes only `strings.<key>`;
   nothing written by say(), el() or a text node holds `.message`, `.reason`, `.detail`, `.stack` or failure.reason. */
const noComments = (code) => code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");
function domLeaks(code) {
  const src = noComments(code), bad = [];
  for (const name of ["say", "el", ".createTextNode", ".replaceChildren", ".appendChild"]) {
    for (const c of callsOf(src, name)) {
      if (/\.(message|reason|detail|stack)\b|failure\b/.test(c.text)) bad.push(name + c.text.slice(0, 50));
    }
  }
  for (const c of callsOf(src, "say")) if (!/^\(\s*strings\.[a-z_]+\s*\)$/.test(c.text)) bad.push("say(" + c.text.slice(1, 40) + " is not a page constant");
  return bad;
}

test("K2: say() takes only page constants, and no .message, .reason or failure.reason flows into say(), el() or a text node", () => {
  let says = 0;
  for (const f of pageFiles) {
    const src = read(f);
    says += callsOf(noComments(src), "say").length;
    assert.deepEqual(domLeaks(src), [], rel(f));
  }
  assert.ok(says >= 4, "the scan found the say() calls it polices: " + says);
});

test("K2 scan control: a planted message or reason flowing into the DOM is found; a page constant is not", () => {
  assert.equal(domLeaks("say(e.message);").length >= 1, true);
  assert.equal(domLeaks("say(failure.reason);").length >= 1, true);
  assert.equal(domLeaks('notice.replaceChildren(doc.createTextNode(e && e.message));').length >= 1, true);
  assert.equal(domLeaks('el("p", {}, [String(err.detail)]);').length >= 1, true);
  assert.equal(domLeaks("say(strings.parts_failed_notice);").length, 0);
  assert.equal(domLeaks("say(text);").length >= 1, true);
});


/* S5: the sheet's proof class comes from the PROOF table (data.js), never from text; the css hiding the list page's lines is scoped
   under the sheet, so the fallback page and a page with scripts off keep every line. */
test("S5: app.js takes the sheet class from SHEET_PROOF_CLASS[proof]; no page code names the class or reads the lines' text", () => {
  const app = noComments(read(path.join(GRAPH, "page", "app.js"))), sheet = noComments(read(path.join(GRAPH, "page", "sheet.js")));
  assert.match(app, /SHEET_PROOF_CLASS\s*\[\s*m\.proof\s*\]/, "the class is looked up by the data's proof");
  for (const [n, src] of [["app.js", app], ["sheet.js", sheet]]) {
    assert.ok(!src.includes("sheet-proof-none"), n + " names the class itself instead of taking it from the table");
    assert.ok(!/roots-only/.test(src), n + " touches the roots-only line");
  }
  assert.ok(read(path.join(GRAPH, "page", "data.js")).includes('none: "sheet-proof-none"'));
});

test("S5: every css rule that hides a list-page line (p.status, p.roots-only) is scoped under the sheet", () => {
  const css = noComments(read(path.join(GRAPH, "graph.css")));
  let seen = 0;
  for (const m of css.matchAll(/([^{}]+)\{[^{}]*\}/g)) {
    const sel = m[1].trim();
    if (!/\.status\b|\.roots-only\b/.test(sel)) continue;
    seen++;
    for (const one of sel.split(",")) assert.match(one.trim(), /^\.graph-sheet\b/, "unscoped rule: " + one.trim());
  }
  assert.ok(seen >= 3, "the rules this polices: " + seen);
});

/* P6/F1: the part, group and file looks. The kind is told by BAR POSITION (never by ring count): part a 6 px top bar, group no bar, file a 4 px
   left bar. Each override must win over the s-none and s-census frames whatever the source order, so it names them in its own selector. The
   selection ring gets a wider gap on THIS map only (engine.css untouched). The look is a placeholder (LOOK PENDING). */
test("P6/F1: graph.css has .face.k-* and .swatch.k-* for part, group and file with the override selectors, the bar widths, and the scoped ring gap", () => {
  const css = read(path.join(GRAPH, "graph.css"));
  assert.match(css, /LOOK PENDING \(Borges proposes, Kepler rules\)/);
  assert.ok(!/k-module/.test(css), "no module look is left");
  const bars = { part: /border-width:\s*6px 2px 2px 2px/, group: /border-width:\s*2px;/, file: /border-width:\s*1px 1px 1px 4px/ };
  for (const k of ["part", "group", "file"]) {
    assert.match(css, new RegExp("\\.swatch\\.k-" + k + "\\s*[,{]"));
    const m = new RegExp("\\.face\\.k-" + k + "\\.s-none[^{]*\\{[^}]*\\}").exec(css);
    assert.ok(m, "an override selector naming .face.k-" + k + ".s-none");
    assert.match(m[0], new RegExp("\\.face\\.k-" + k + "\\.s-census"));
    assert.match(m[0], bars[k], k);
    assert.ok(!/double/.test(m[0]), "no ring-count (double) mark");
  }
  assert.match(css, /\.ge-node\.ge-selected:has\(\.face\.k-part, \.face\.k-group, \.face\.k-file\)\s*\{\s*outline-offset:\s*3px;\s*\}/);
  const engine = read(path.join(GRAPH, "engine", "engine.css"));
  assert.ok(!/outline-offset:\s*3px/.test(engine), "engine.css is untouched by this map's ring gap");
});

test("A1: the page decides nothing by a kind NAME (part, group, file, module appear in no page logic)", () => {
  for (const f of pageFiles) {
    const code = read(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    for (const name of ["part", "group", "file", "module"]) {
      const quoted = new RegExp("[\"'`]" + name + "[\"'`]");
      if (rel(f) === "page/data.js") { const noTable = code.replace(/export const KIND_CLASS[^\n]*\n/, ""); assert.ok(!quoted.test(noTable), rel(f) + " names kind " + name); }
      else assert.ok(!quoted.test(code), rel(f) + " names kind " + name);
    }
  }
});

/* A6: every place the page draws a step title goes through the ONE helper (dom.js titleChildren). */
test("A6: face.js and sheet.js draw a title only through titleChildren; no raw title is handed to el()", () => {
  for (const [f, raw] of [["face.js", /\[\s*d\.title\s*\]/], ["sheet.js", /kids\.push\(\s*c\.title\s*\)/]]) {
    const src = read(path.join(GRAPH, "page", f));
    assert.match(src, /titleChildren\(/, f);
    assert.ok(!raw.test(src), f + " still draws the raw title");
  }
});
