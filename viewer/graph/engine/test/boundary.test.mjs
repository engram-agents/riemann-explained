// BOUNDARY: no engine file uses an HTML-string API, code evaluation, a global, a remote address, or an import
// from outside engine/; it names no page string, step id, address or card class. Tests are not engine files.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
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
const FORBIDDEN = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser", "createContextualFragment", "eval(", "new Function", "http:", "https:", "createElementNS", "<svg", "<canvas"];
const GLOBALS = ["window", "globalThis", "document.", "localStorage", "sessionStorage", "fetch(", "XMLHttpRequest", "location.", "navigator."];
const PAGE_WORDS = [/riemann/i, /\bcard\b/i, /\.\.\/page/, /\brh-/, /\blean\b/i];
const src = (p) => readFileSync(p, "utf8");

test("the engine has files to scan (a scan over nothing proves nothing)", () => {
  const names = FILES.map((p) => relative(ENGINE, p)).sort();
  for (const must of ["INTERFACE.md", "index.js", "controller.js", "layout.js", "dom.js"]) assert.ok(names.includes(must), "missing " + must + " in " + names);
});
test("no engine file contains a forbidden token or any address (no exemption)", () => {
  for (const p of FILES) { const t = src(p); for (const tok of FORBIDDEN) assert.ok(!t.includes(tok), relative(ENGINE, p) + " contains " + tok); }
});
test("a string setTimeout or setInterval is absent", () => {
  for (const p of FILES) assert.ok(!/set(Timeout|Interval)\s*\(\s*["'`]/.test(src(p)), relative(ENGINE, p));
});
test("no engine file touches a global, the document or the network", () => {
  for (const p of FILES.filter((f) => f.endsWith(".js"))) { const t = src(p); for (const tok of GLOBALS) assert.ok(!t.includes(tok), relative(ENGINE, p) + " contains " + tok); }
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
