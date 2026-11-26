import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { makeFakeDoc } from "./fakedoc.mjs";
import { makeEl } from "../dom.js";
import * as NOTE from "../note.js";      // read through the namespace so a missing module is one red file, with its own message

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL_NOTE = readFileSync(path.join(HERE, "fixtures", "note-onesidedbound.txt"), "utf8");
const ALLOWED = new Set(["H3", "H4", "H5", "P", "UL", "OL", "LI", "CODE", "PRE", "TABLE", "THEAD", "TBODY", "TR", "TH", "TD"]);

const render = (text) => NOTE.renderNote(text, makeEl(makeFakeDoc()));

/* A compact, exact picture of a node: tag, class, attributes, children; a text node as a JSON string. */
function ser(n) {
  if (n.nodeType === 3) return JSON.stringify(n.textContent);
  const a = Object.keys(n.attrs).filter((k) => k !== "class").map((k) => "{" + k + "=" + n.attrs[k] + "}").join("");
  const c = n.attrs.class ? "." + n.attrs.class : "";
  return n.tagName.toLowerCase() + c + a + "(" + n.children.map(ser).join("|") + ")";
}
const top = (text) => render(text).children.map(ser);
function walk(n, f) { f(n); for (const c of n.children || []) walk(c, f); }
function elements(frag) { const out = []; walk(frag, (n) => { if (n.nodeType === 1) out.push(n); }); return out; }
function allText(frag) { let s = ""; walk(frag, (n) => { if (n.nodeType === 3) s += n.textContent; }); return s; }

test("renderNote returns a document fragment", () => {
  const f = render("hello");
  assert.equal(f.nodeType, 11);
  assert.deepEqual(render("").children, []);
  assert.deepEqual(render("\n\n   \n").children, []);
});

test("N1 headings: '#' is h3, '##' is h4, '###' and deeper are h5; every heading has the class note-h; text goes through the inline rule", () => {
  assert.deepEqual(top("# A\n\n## B `c` d\n\n### C\n\n#### D\n\n###### E\n\ntext"),
    ['h3.note-h("A")', 'h4.note-h("B "|code("c")|" d")', 'h5.note-h("C")', 'h5.note-h("D")', 'h5.note-h("E")', 'p("text")']);
  // a heading needs a space; seven hashes are not a heading; a heading directly followed by text ends there
  assert.deepEqual(top("#nospace\n\n####### seven\n\n# H\nbody"), ['p("#nospace")', 'p("####### seven")', 'h3.note-h("H")', 'p("body")']);
});

test("N2 bullets with '*' and '-', nesting, and the two-space continuation", () => {
  assert.deepEqual(top("* a\n  * b\n    - c\n* d\n  continued here\n- e"),
    ['ul(li("a"|ul(li("b"|ul(li("c")))))|li("d continued here")|li("e"))']);
  // a list directly after a paragraph line (no blank line) is a list, as in the real notes
  assert.deepEqual(top("Notions:\n* x\n* y"), ['p("Notions:")', 'ul(li("x")|li("y"))']);
  // a non-indented line after a list ends it and is a paragraph
  assert.deepEqual(top("* x\nplain"), ['ul(li("x"))', 'p("plain")']);
});

test("N2 the REAL OneSidedBound.lean note: heading, paragraphs, a three-item list whose second item continues on an indented line", () => {
  const f = render(REAL_NOTE);
  const kids = f.children;
  assert.equal(kids[0].tagName, "H3");
  assert.equal(kids[0].attrs.class, "note-h");
  assert.equal(allText({ children: [kids[0]], nodeType: 1 }), "The one-sided bound, and the theorem in half-plane form");
  assert.deepEqual(kids.map((k) => k.tagName), ["H3", "P", "P", "UL"]);
  const ul = kids[3];
  assert.equal(ul.children.length, 3);
  assert.equal(ul.children.filter((li) => li.tagName === "LI").length, 3);
  const li2 = ser(ul.children[1]);
  assert.ok(li2.includes('". Here "'), li2);
  assert.ok(li2.includes('code("λ(n) = Λ(n) (1 - chiK d n)")'), li2);
  assert.ok(li2.includes('" for "'), li2);
  const text = allText(f);
  assert.ok(!text.includes("\n"), "no newline survives into a text node");
  assert.ok(!/ {2}\S/.test(text.replace(/ /g, "")), "the continuation indent is gone");
  assert.ok(!text.includes("`"), "every backtick in this note is part of a pair");
  assert.deepEqual([...new Set(elements(f).map((e) => e.tagName))].sort(), ["CODE", "H3", "LI", "P", "UL"]);
});

test("N3 a numbered list: <ol> with `start` from the first item's integer, and nothing else", () => {
  assert.deepEqual(top("3. a\n4. b\n\ntext\n\n7) c"), ['ol{start=3}(li("a")|li("b"))', 'p("text")', 'ol{start=7}(li("c"))']);
  assert.deepEqual(top("* x\n  1. y\n  2. z"), ['ul(li("x"|ol{start=1}(li("y")|li("z"))))']);
  assert.deepEqual(top("012. zero lead"), ['ol{start=12}(li("zero lead"))']);
  assert.deepEqual(top("1234567890. ten digits"), ['p("1234567890. ten digits")'], "ten digits is not a list marker");
  for (const e of elements(render("3. a\n4. b\n* x\n  - y"))) {
    const keys = Object.keys(e.attrs);
    assert.ok(keys.length === 0 || (e.tagName === "OL" && keys.length === 1 && keys[0] === "start"), e.tagName + " " + keys);
  }
});

test("N4 an indented block outside a list is ONE <pre>: the common 4-space indent removed, blank lines kept, no inline processing, no <code> inside", () => {
  const f = render("para\n\n    f(x) = `a`\n      + b * c_d\n\n    next\n\nafter");
  assert.deepEqual(f.children.map((k) => k.tagName), ["P", "PRE", "P"]);
  const pre = f.children[1];
  assert.equal(pre.children.length, 1);
  assert.equal(pre.children[0].nodeType, 3);
  assert.equal(pre.children[0].textContent, "f(x) = `a`\n  + b * c_d\n\nnext");
  assert.equal(elements(f).filter((e) => e.tagName === "CODE").length, 0);
  // an indented line inside a paragraph run continues the paragraph; inside a list it continues the item
  assert.deepEqual(top("text\n    more"), ['p("text more")']);
  assert.deepEqual(top("* item\n      deep"), ['ul(li("item deep"))']);
});

test("N5 a pipe table with a header: <thead><th>, <tbody><td>; without a separator everything is body", () => {
  assert.deepEqual(top("| h1 | h2 |\n| --- | :-: |\n| x | y |\n| z | `w` |"),
    ['table(thead(tr(th("h1")|th("h2")))|tbody(tr(td("x")|td("y"))|tr(td("z")|td(code("w")))))']);
  assert.deepEqual(top("| a | b |\n| c | d |"), ['table(tbody(tr(td("a")|td("b"))|tr(td("c")|td("d"))))']);
  assert.deepEqual(top("  | a | b\n  | c | d"), ['table(tbody(tr(td("a")|td("b"))|tr(td("c")|td("d"))))'], "no trailing pipe; indented under 4 spaces");
  assert.deepEqual(top("| only |"), ['p("| only |")'], "one pipe line is a paragraph");
  assert.deepEqual(top("text\n| a | b |\n| c | d |"), ['p("text")', 'table(tbody(tr(td("a")|td("b"))|tr(td("c")|td("d"))))']);
});

test("N6 a table whose rows have different cell counts is ONE <pre> of the literal lines, never a guessed table", () => {
  assert.deepEqual(top("| a | b |\n| c |"), ['pre("| a | b |\\n| c |")']);
  assert.deepEqual(top("| a | b |\n|---|\n| 1 | 2 |"), ['pre("| a | b |\\n|---|\\n| 1 | 2 |")']);
  assert.deepEqual(top("| a | b |\n| c | d | e |"), ['pre("| a | b |\\n| c | d | e |")']);
  assert.equal(elements(render("| a | b |\n| c |")).filter((e) => ["TABLE", "TR", "TD", "TH"].includes(e.tagName)).length, 0);
});

test("N7 a pipe inside a code span does not split the cell", () => {
  assert.deepEqual(top("| a | `x|y` | c |\n|---|---|---|\n| 1 | 2 | 3 |"),
    ['table(thead(tr(th("a")|th(code("x|y"))|th("c")))|tbody(tr(td("1")|td("2")|td("3"))))']);
  assert.deepEqual(top("| `a|b` |\n| `c` |"), ['table(tbody(tr(td(code("a|b")))|tr(td(code("c")))))']);
  // an unpaired backtick is not a span, so its pipe does split
  assert.deepEqual(top("| `a | b |\n| c | d |"), ['table(tbody(tr(td("`a")|td("b"))|tr(td("c")|td("d"))))']);
});

test("N8 NO emphasis: '*' and '_' outside code are literal characters", () => {
  assert.deepEqual(top("a *b* c_d_e"), ['p("a *b* c_d_e")']);
  assert.deepEqual(top("**bold** _it_ __x__ x*y*z"), ['p("**bold** _it_ __x__ x*y*z")']);
  assert.deepEqual(top("* a *b* c_d_e"), ['ul(li("a *b* c_d_e"))']);
  assert.deepEqual(top("| *a* | _b_ |\n| c | d |"), ['table(tbody(tr(td("*a*")|td("_b_"))|tr(td("c")|td("d"))))']);
  assert.deepEqual(top("# *h* _h_"), ['h3.note-h("*h* _h_")']);
  assert.deepEqual(top("`*a*` `_b_`"), ['p(code("*a*")|" "|code("_b_"))']);
  // a backslash is a literal character, an entity is six characters
  assert.deepEqual(top("a\\*b &amp; &lt;"), ['p("a\\\\*b &amp; &lt;")']);
});

test("N9 HOSTILE: markup, entities, a javascript: word and a markdown link all render as visible text; only the allowed elements; the only attribute is `start` on <ol>", () => {
  const hostile = [
    "<script>alert(1)</script>", "<img src=x onerror=1>", "&amp;lt;", "javascript:", "[x](javascript:y)",
  ];
  const note = "# " + hostile[0] + "\n\n" + hostile.join(" ") + "\n\n* " + hostile[1] + "\n* `" + hostile[0] + "`\n\n9. " + hostile[4] +
    "\n\n    " + hostile[0] + "\n\n| " + hostile[1] + " | " + hostile[3] + " |\n|---|---|\n| " + hostile[4] + " | " + hostile[2] + " |\n";
  const f = render(note);
  const els = elements(f);
  assert.ok(els.length > 10);
  for (const e of els) {
    assert.ok(ALLOWED.has(e.tagName), "element outside the allowed set: " + e.tagName);
    for (const k of Object.keys(e.attrs)) assert.ok(k === "class" || (k === "start" && e.tagName === "OL"), "attribute " + k + " on " + e.tagName);
    if (e.attrs.class !== undefined) assert.equal(e.attrs.class, "note-h");
  }
  const text = allText(f);
  for (const h of hostile) assert.ok(text.includes(h), "visible as text: " + h);
  // the paragraph is one text node holding all five, verbatim
  assert.ok(f.children[1].children.length === 1 && f.children[1].children[0].textContent === hostile.join(" "));
});

test("N9 every element the renderer builds goes through el(): a stand-in el that records its calls sees every tag, and no attribute besides class and start", () => {
  const doc = makeFakeDoc(), real = makeEl(doc), calls = [];
  const el = (tag, attrs, kids) => { calls.push([tag, Object.keys(attrs || {})]); return real(tag, attrs, kids); };
  NOTE.renderNote("# H\n\ntext `c`\n\n1. a\n\n* b\n\n    pre\n\n| a | b |\n|---|---|\n| c | d |", el);
  assert.ok(calls.length >= 12);
  for (const [tag, keys] of calls) {
    assert.ok(["h3", "p", "code", "ol", "ul", "li", "pre", "table", "thead", "tbody", "tr", "th", "td"].includes(tag), tag);
    for (const k of keys) assert.ok(k === "class" || k === "start", k);
  }
  assert.equal(doc.made.length, calls.length, "no element is made except through el()");
});

test("renderNote is pure: same text, same picture; CRLF is LF; a lone CR is a literal character", () => {
  assert.deepEqual(top("# A\r\n\r\ntext\r\nmore"), top("# A\n\ntext\nmore"));
  assert.deepEqual(top(REAL_NOTE), top(REAL_NOTE));
});

test("nesting is capped so a hostile note cannot recurse without bound; a deeper marker is then a continuation of its item", () => {
  const deep = Array.from({ length: 5000 }, (_, i) => " ".repeat(i) + "* x").join("\n");
  const f = render(deep);
  let depth = 0;
  const d = (n, k) => { depth = Math.max(depth, k); for (const c of n.children || []) if (c.tagName === "UL") d(c, k + 1); else if (c.tagName === "LI") d(c, k); };
  d(f, 0);
  assert.ok(depth >= 2 && depth <= 8, "depth " + depth);
});

test("templateParts fills {source} and {commit} as TEXT: the template is split, never replaced into markup", () => {
  assert.deepEqual(NOTE.templateParts("Source file: {source} · version {commit} of x", { source: "a/b.lean", commit: "01234567" }),
    ["Source file: ", "a/b.lean", " · version ", "01234567", " of x"]);
  assert.deepEqual(NOTE.templateParts("{source}{source}", { source: "<b>x</b>", commit: "c" }), ["<b>x</b>", "<b>x</b>"]);
  assert.deepEqual(NOTE.templateParts("no placeholders <b>", { source: "s", commit: "c" }), ["no placeholders <b>"]);
  assert.deepEqual(NOTE.templateParts("{n} {nothing} {commit}", { source: "s", commit: "$&" }), ["{n} {nothing} ", "$&"]);
});

test("note.js is small, pure and imports only dom.js: no document, window, fetch, timers, randomness, innerHTML-style sinks or raw element creation", () => {
  const src = readFileSync(path.join(HERE, "..", "note.js"), "utf8");
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");
  assert.deepEqual([...src.matchAll(/^import .* from "([^"]+)";/gm)].map((m) => m[1]), ["./dom.js"]);
  for (const bad of ["document", "window", "globalThis", "fetch", "setTimeout", "Math.random", "Date", "createElement", "setAttribute", "innerHTML", "textContent"])
    assert.ok(!code.includes(bad), "note.js uses " + bad);
  assert.ok(src.split("\n").length <= 330, "note.js stays small: " + src.split("\n").length + " lines");
});
