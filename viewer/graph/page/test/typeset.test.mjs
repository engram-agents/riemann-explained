/* THE MATHS FACE (step 1) at node level: a backtick span that is ONE LETTER or FORMULA-ONLY is set in the page's maths face
   (<span class="m">, plus "m1" for one letter); a name, a name with arguments and a name in a formula stay <code>; an unsure class is code.
   Appearance only. renderNote's third argument turns it on; without it the note renders exactly as before.
   Fixtures (committed inputs, made by fixtures/make_fixtures.py): note-spans-classes.json (Sol's cls3 over the 6,459 distinct real spans, byte
   for byte), note-onesidedbound.txt and note-linecoordinates.txt (the two real notes). Nothing here reads a host path. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { makeFakeDoc } from "./fakedoc.mjs";
import { makeEl } from "../dom.js";
import * as NOTE from "../note.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIX = path.join(HERE, "fixtures");
const ONE_SIDED = readFileSync(path.join(FIX, "note-onesidedbound.txt"), "utf8");
const LINE_COORDS = readFileSync(path.join(FIX, "note-linecoordinates.txt"), "utf8");
const ALLOWED = new Set(["H3", "H4", "H5", "P", "UL", "OL", "LI", "CODE", "PRE", "TABLE", "THEAD", "TBODY", "TR", "TH", "TD", "SPAN", "SUP", "SUB"]);
const SPAN_RULE = /(?<!`)`([^`\r\n]+)`(?!`)/g;

const elOf = () => makeEl(makeFakeDoc());
const renderT = (text) => NOTE.renderNote(text, elOf(), true);
const renderPlain = (text) => NOTE.renderNote(text, elOf());

function ser(n) {
  if (n.nodeType === 3) return JSON.stringify(n.textContent);
  const a = Object.keys(n.attrs).filter((k) => k !== "class").map((k) => "{" + k + "=" + n.attrs[k] + "}").join("");
  const c = n.attrs.class ? "." + n.attrs.class : "";
  return n.tagName.toLowerCase() + c + a + "(" + n.children.map(ser).join("|") + ")";
}
const topT = (text) => renderT(text).children.map(ser);
function walk(n, f) { f(n); for (const c of n.children || []) walk(c, f); }
function elements(frag) { const out = []; walk(frag, (n) => { if (n.nodeType === 1) out.push(n); }); return out; }
function allText(frag) { let s = ""; walk(frag, (n) => { if (n.nodeType === 3) s += n.textContent; }); return s; }
const flat = (s) => s.replace(/\s+/g, "");
const J = JSON.stringify;
/* What a set span may lose (maths_scripts.test.mjs states the whole contract): a script character, a space, a brace or a paren, and nothing is reordered. */
function onlyAllowedLoss(span, out) {
  const cs = [...span], os = [...out];
  let j = 0;
  for (const c of cs) {
    if (j < os.length && os[j] === c) { j++; continue; }
    if (!"^_ {}()".includes(c)) return false;
  }
  return j === os.length;
}

test("T1 EQUALITY OVER THE WHOLE CLASS: spanClass and oneLetter agree with Sol's cls3 on EVERY one of the 6,459 real distinct spans", () => {
  const raw = readFileSync(path.join(FIX, "note-spans-classes.json"));
  assert.equal(createHash("sha256").update(raw).digest("hex"), "026713972092ac9784949e83cd77743525c97a213090d328a5ed5db2135ae8e2", "the fixture is Sol's file, byte for byte");
  assert.equal(raw.length, 585259);
  const meta = JSON.parse(raw.toString("utf8"));
  assert.equal(meta.distinct, 6459);
  assert.equal(meta.spans.length, 6459);
  assert.equal(typeof NOTE.spanClass, "function", "note.js exports spanClass");
  assert.equal(typeof NOTE.oneLetter, "function", "note.js exports oneLetter");
  const bad = [], per = {};
  let n = 0;
  for (const r of meta.spans) {
    n++;
    per[r.class] = (per[r.class] || 0) + 1;
    const c = NOTE.spanClass(r.span), o = NOTE.oneLetter(r.span);
    if (c !== r.class || o !== r.one_letter) bad.push({ span: r.span, want: [r.class, r.one_letter], got: [c, o] });
  }
  console.log("T1 rows checked: " + n + "; by class " + J(per) + "; one_letter true " + meta.spans.filter((r) => r.one_letter).length + "; rows that differ: " + bad.length);
  assert.equal(n, 6459, "rows checked");
  assert.deepEqual(Object.keys(per).sort(), ["formula", "name", "name-in-formula", "name-with-arguments"], "every class occurs, so the equality is not vacuous");
  assert.equal(bad.length, 0, bad.length + " of " + n + " rows differ; first: " + J(bad.slice(0, 5)));
});

test("T2 the named anchors from Sol's measurement: formula spans are span.m, one letters are span.m.m1, every other class stays code", () => {
  const formula = ["U(1)", "(c, s, c')", "V°", "γ f", "K = ℚ(√-d)"];
  const withArgs = ["S.frameProducts γ", "D.levelPrime 0", "PadicPlace p"];
  const inFormula = ["X ⊕ Unit", "M = S.M", "Gal(Ω/E)", "z = false", "h_c⁻¹ γ h_c'"];
  for (const sp of formula) { assert.equal(NOTE.spanClass(sp), "formula", sp); assert.deepEqual(topT("`" + sp + "`"), ["p(span.m(" + J(sp) + "))"], sp); }
  for (const sp of withArgs) { assert.equal(NOTE.spanClass(sp), "name-with-arguments", sp); assert.deepEqual(topT("`" + sp + "`"), ["p(code(" + J(sp) + "))"], sp); }
  for (const sp of inFormula) { assert.equal(NOTE.spanClass(sp), "name-in-formula", sp); assert.deepEqual(topT("`" + sp + "`"), ["p(code(" + J(sp) + "))"], sp); }
  // a formula span with a script is set or refused by scriptParts (maths_scripts.test.mjs): here a combining mark stands before the _, G1 gives it no base, so it is code as typed
  assert.equal(NOTE.spanClass("ℚ̄_ℓ"), "formula");
  assert.deepEqual(topT("`ℚ̄_ℓ`"), ["p(code(" + J("ℚ̄_ℓ") + "))"]);
  for (const sp of ["Parameters", "S.frameProducts", "x₁"]) assert.equal(NOTE.spanClass(sp), "name", sp);
  assert.deepEqual(topT("`Parameters`"), ['p(code("Parameters"))']);
  for (const sp of ["x", "γ"]) {
    assert.equal(NOTE.oneLetter(sp), true, sp);
    assert.deepEqual(topT("`" + sp + "`"), ["p(span.m m1(" + J(sp) + "))"], sp);
  }
  // one letter means ONE code point that is a letter: a digit, a symbol, two letters and a letter with a combining mark are not
  for (const sp of ["1", "+", "xy", "ℚ̄", "ℓ₁"]) assert.equal(NOTE.oneLetter(sp), false, sp);
  // the span's text node holds the characters exactly; the text around it is untouched
  assert.deepEqual(topT("a `x` b `U(1)` c `Parameters`."), ['p("a "|span.m m1("x")|" b "|span.m("U(1)")|" c "|code("Parameters")|".")']);
});

test("T2b UNSURE STAYS CODE: a name-in-formula span and a name-with-arguments span render as <code>, never span.m", () => {
  for (const sp of ["h_c⁻¹ γ h_c'", "X ⊕ Unit", "S.frameProducts γ", "D.levelPrime 0"]) {
    const f = renderT("`" + sp + "`");
    assert.deepEqual(elements(f).map((e) => e.tagName), ["P", "CODE"], sp);
    assert.equal(elements(f).filter((e) => e.tagName === "SPAN").length, 0, sp);
  }
});

test("without the flag the note renders exactly as before; exactNote is ONE <pre> holding the text verbatim, with no attribute", () => {
  assert.deepEqual(renderPlain("`U(1)` `x`").children.map(ser), ['p(code("U(1)")|" "|code("x"))']);
  assert.deepEqual(NOTE.renderNote("`U(1)`", elOf(), false).children.map(ser), ['p(code("U(1)"))']);
  assert.deepEqual(renderPlain(LINE_COORDS).children.map(ser), NOTE.renderNote(LINE_COORDS, elOf(), undefined).children.map(ser));
  const text = "\n# T `a`\r\n  * `x` b\n```\n";
  assert.equal(typeof NOTE.exactNote, "function", "note.js exports exactNote");
  const pre = NOTE.exactNote(text, elOf());
  assert.equal(pre.tagName, "PRE");
  assert.equal(pre.children.length, 1);
  assert.equal(pre.children[0].nodeType, 3);
  assert.equal(pre.children[0].textContent, text);
  assert.deepEqual(Object.keys(pre.attrs), []);
});

test("T3 READ-BACK over the OneSidedBound and LineCoordinates real notes: the maths face changes appearance only, apart from the script characters, the spaces round a ^ and the brackets of an operand", () => {
  for (const [name, note] of [["OneSidedBound", ONE_SIDED], ["LineCoordinates", LINE_COORDS]]) {
    const spans = [...note.matchAll(SPAN_RULE)].map((m) => m[1]);
    assert.ok(spans.length >= 10, name + " has spans: " + spans.length);
    const typeset = renderT(note), plain = renderPlain(note);
    // every character in the same order as the round-1 rendering has them, and as the note has them with its backtick characters removed
    // (the note's own line markers and whitespace are structure, so they are set aside on BOTH sides)
    assert.ok(onlyAllowedLoss(allText(plain), allText(typeset)), name + ": the round-1 text content, with only script characters, spaces round a ^ and operand brackets removed, in order");
    const marked = note.split("\n").map((l) => l.replace(/^\s*(#{1,6}\s+|[*-]\s+|\d{1,9}[.)]\s+)/, "")).join("\n").replace(/`/g, "");
    assert.ok(onlyAllowedLoss(flat(marked), flat(allText(typeset))), name + ": the note with its backticks (and line markers) removed, in order, less only those characters");
    assert.ok(!allText(typeset).includes("`"), name);
    // span by span: the spans in the note, in order, are the code and maths elements in the page, in order, each holding its text exactly
    const shown = elements(typeset).filter((e) => e.tagName === "CODE" || e.attrs.class === "m" || e.attrs.class === "m m1");
    assert.equal(shown.length, spans.length, name);
    shown.forEach((e, k) => {
      const t = allText(e);
      if (e.tagName === "CODE" || !/[\^_]/.test(spans[k])) assert.deepEqual(e.children.map((c) => c.textContent), [spans[k]], name + " span " + k);   // as typed, ONE text node
      else assert.ok(onlyAllowedLoss(spans[k], t) && !/[\^_]/.test(t), name + " set span " + k);
    });
    const maths = shown.filter((e) => e.tagName === "SPAN").length;
    assert.ok(maths >= 1 && maths < spans.length, name + ": some spans are maths face and some stay code: " + maths + " of " + spans.length);
  }
});

test("T4 MARKUP: a maths-face span is exactly one span.m (or span.m m1) holding ONE text node, or text nodes and attribute-less sup and sub when it has scripts; no element outside the allowed set, no attribute but `class` and `start` on <ol>", () => {
  const notes = [ONE_SIDED, LINE_COORDS,
    "# `x` `U(1)`\n\n* `a<b>c` `<b>x</b>` `x&y`\n3. `γ f`\n\n| `x` | `V°` |\n|---|---|\n| `<i>` | `a<i>b` |\n"];
  let maths = 0;
  for (const note of notes) {
    for (const e of elements(renderT(note))) {
      assert.ok(ALLOWED.has(e.tagName), "element outside the allowed set: " + e.tagName);
      for (const k of Object.keys(e.attrs)) assert.ok(k === "class" || (k === "start" && e.tagName === "OL"), "attribute " + k + " on " + e.tagName);
      if (e.attrs.class !== undefined) assert.ok(["note-h", "m", "m m1"].includes(e.attrs.class), "class " + e.attrs.class);
      if (e.tagName === "SPAN") {
        maths++;
        assert.ok(e.attrs.class === "m" || e.attrs.class === "m m1", String(e.attrs.class));
        if (!e.children.some((c) => c.nodeType === 1)) {
          assert.equal(e.children.length, 1, "one child");
          assert.equal(e.children[0].nodeType, 3, "which is a text node");
        } else {
          assert.equal(e.attrs.class, "m");
          walk(e, (x) => { if (x.nodeType === 1 && x !== e) assert.ok(x.tagName === "SUP" || x.tagName === "SUB", x.tagName); });
        }
      }
    }
  }
  assert.ok(maths >= 15, "maths spans walked: " + maths);
  // markup characters inside a maths span are that text and nothing else
  assert.deepEqual(topT("`<b>x</b>`"), ['p(span.m("<b>x</b>"))']);
  assert.deepEqual(topT("`a<i>b`"), ['p(span.m("a<i>b"))']);
  // every element goes through el(): a stand-in that records its calls sees span with the class, and nothing else
  const doc = makeFakeDoc(), real = makeEl(doc), calls = [];
  const el = (tag, attrs, kids) => { calls.push([tag, J(attrs || {})]); return real(tag, attrs, kids); };
  NOTE.renderNote("`x` `U(1)` `Foo`", el, true);
  assert.deepEqual(calls.filter((c) => c[0] === "span" || c[0] === "code").map((c) => c.join(" ")), ['span {"class":"m m1"}', 'span {"class":"m"}', 'code {}']);
  assert.equal(doc.made.length, calls.length, "no element is made except through el()");
});
