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
